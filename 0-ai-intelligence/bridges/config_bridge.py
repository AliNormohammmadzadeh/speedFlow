"""AI-to-Configuration Bridge: Config Agent -> GitOps / Terraform pipeline."""

import json
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigBridge:
    def __init__(self):
        self.gitops_path = Path(os.environ.get("GITOPS_REPO_PATH", "/gitops"))
        self.dry_run = os.environ.get("GITOPS_DRY_RUN", "true").lower() == "true"
        self.git_push = os.environ.get("GITOPS_GIT_PUSH", "false").lower() == "true"
        self.git_branch = os.environ.get("GITOPS_BRANCH", "main")
        self.git_remote = os.environ.get("GITOPS_GIT_REMOTE", "")

    def deploy(self, config_output: dict) -> dict:
        """Write configs and optionally trigger GitOps sync."""
        self.gitops_path.mkdir(parents=True, exist_ok=True)

        manifest_dir = self.gitops_path / "k8s"
        tf_dir = self.gitops_path / "terraform"
        manifest_dir.mkdir(exist_ok=True)
        tf_dir.mkdir(exist_ok=True)

        deployed = {"k8s_manifests": 0, "terraform_files": 0, "airflow_triggered": False}

        for manifest in config_output.get("kubernetes", []):
            name = manifest.get("metadata", {}).get("name", "unknown")
            path = manifest_dir / f"{name}.json"
            with open(path, "w") as f:
                json.dump(manifest, f, indent=2)
            deployed["k8s_manifests"] += 1

        tf_path = tf_dir / "generated.tf.json"
        with open(tf_path, "w") as f:
            json.dump(config_output.get("terraform", {}), f, indent=2)
        deployed["terraform_files"] = 1

        # Emit an ArgoCD Application so a GitOps controller auto-syncs the k8s dir.
        deployed["argocd_app"] = self._write_argocd_app()

        # Commit + push manifests so ArgoCD (watching the repo) picks them up.
        if self.git_push:
            deployed["git_push"] = self._git_push()

        if not self.dry_run:
            deployed["gitops_result"] = self._trigger_gitops()
        else:
            deployed["gitops_result"] = "dry_run — set GITOPS_DRY_RUN=false to apply"
            logger.info("GitOps dry-run: configs written to %s", self.gitops_path)

        airflow_params = config_output.get("airflow_params", {})
        if airflow_params.get("dag_id"):
            deployed["airflow_triggered"] = self._trigger_airflow_dag(airflow_params)

        return deployed

    def _write_argocd_app(self) -> str:
        """Write an ArgoCD Application manifest for automated sync of k8s/."""
        app = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {"name": "speedflow-platform", "namespace": "argocd"},
            "spec": {
                "project": "default",
                "source": {
                    "repoURL": os.environ.get("GITOPS_GIT_REMOTE", "https://github.com/your-org/speedflow-gitops.git"),
                    "targetRevision": self.git_branch,
                    "path": "k8s",
                },
                "destination": {"server": "https://kubernetes.default.svc", "namespace": "speedflow"},
                "syncPolicy": {
                    "automated": {"prune": True, "selfHeal": True},
                    "syncOptions": ["CreateNamespace=true"],
                },
            },
        }
        argocd_dir = self.gitops_path / "argocd"
        argocd_dir.mkdir(exist_ok=True)
        path = argocd_dir / "speedflow-platform.json"
        with open(path, "w") as f:
            json.dump(app, f, indent=2)
        return str(path)

    def _git_push(self) -> str:
        """Commit generated manifests and push so ArgoCD auto-syncs."""
        try:
            if not (self.gitops_path / ".git").exists():
                subprocess.run(["git", "init", "-q"], cwd=self.gitops_path, check=True, timeout=15)
                subprocess.run(["git", "checkout", "-q", "-B", self.git_branch], cwd=self.gitops_path, timeout=15)
            # Ensure identity for non-interactive commits.
            subprocess.run(["git", "config", "user.email", "config-agent@speedflow.local"], cwd=self.gitops_path, timeout=10)
            subprocess.run(["git", "config", "user.name", "SpeedFlow Config Agent"], cwd=self.gitops_path, timeout=10)
            subprocess.run(["git", "add", "-A"], cwd=self.gitops_path, check=True, timeout=15)
            commit = subprocess.run(
                ["git", "commit", "-q", "-m", "chore(config-agent): sync generated manifests"],
                cwd=self.gitops_path, capture_output=True, text=True, timeout=15,
            )
            if self.git_remote:
                push = subprocess.run(
                    ["git", "push", self.git_remote, self.git_branch],
                    cwd=self.gitops_path, capture_output=True, text=True, timeout=60,
                )
                return f"pushed to {self.git_remote}:{self.git_branch} ({push.returncode})"
            return commit.stdout or commit.stderr or "committed (no remote configured)"
        except Exception as e:
            logger.warning("git push failed: %s", e)
            return f"git push error: {e}"

    def _trigger_gitops(self) -> str:
        """Apply via kubectl (local) or ArgoCD CLI (production)."""
        manifest_dir = self.gitops_path / "k8s"
        try:
            result = subprocess.run(
                ["kubectl", "apply", "-f", str(manifest_dir)],
                capture_output=True, text=True, timeout=30,
            )
            return result.stdout or result.stderr
        except FileNotFoundError:
            return "kubectl not available — configs written for manual/ArgoCD sync"

    def _trigger_airflow_dag(self, params: dict) -> bool:
        airflow_url = os.environ.get("AIRFLOW_URL", "http://airflow:8080")
        try:
            import httpx
            with httpx.Client(timeout=10) as client:
                resp = client.post(
                    f"{airflow_url}/api/v1/dags/{params['dag_id']}/dagRuns",
                    json={"conf": params.get("conf", {})},
                    auth=("admin", "admin"),
                )
                return resp.status_code in (200, 201)
        except Exception as e:
            logger.warning("Airflow trigger failed: %s", e)
            return False
