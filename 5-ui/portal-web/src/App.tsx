import { Routes, Route, Outlet } from 'react-router-dom'
import Layout from './components/Layout'
import Landing from './pages/Landing'
import Overview from './pages/Overview'
import Showcase from './pages/Showcase'
import PipelineCanvas from './pages/PipelineCanvas'
import Ingestion from './pages/Ingestion'
import Stream from './pages/Stream'
import AIAgents from './pages/AIAgents'
import Brain from './pages/Brain'
import Applications from './pages/Applications'
import Tenants from './pages/Tenants'
import Billing from './pages/Billing'
import Verticals from './pages/Verticals'
import Trading from './pages/Trading'

function DashboardLayout() {
  return (
    <Layout>
      <Outlet />
    </Layout>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route element={<DashboardLayout />}>
        <Route path="/overview" element={<Overview />} />
        <Route path="/showcase" element={<Showcase />} />
        <Route path="/canvas" element={<PipelineCanvas />} />
        <Route path="/ingestion" element={<Ingestion />} />
        <Route path="/stream" element={<Stream />} />
        <Route path="/ai" element={<AIAgents />} />
        <Route path="/brain" element={<Brain />} />
        <Route path="/apps" element={<Applications />} />
        <Route path="/trading" element={<Trading />} />
        <Route path="/verticals" element={<Verticals />} />
        <Route path="/tenants" element={<Tenants />} />
        <Route path="/billing" element={<Billing />} />
      </Route>
    </Routes>
  )
}
