import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Overview from './pages/Overview'
import PipelineCanvas from './pages/PipelineCanvas'
import Ingestion from './pages/Ingestion'
import Stream from './pages/Stream'
import AIAgents from './pages/AIAgents'
import Applications from './pages/Applications'
import Tenants from './pages/Tenants'
import Billing from './pages/Billing'
import Verticals from './pages/Verticals'
import Trading from './pages/Trading'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/canvas" element={<PipelineCanvas />} />
        <Route path="/ingestion" element={<Ingestion />} />
        <Route path="/stream" element={<Stream />} />
        <Route path="/ai" element={<AIAgents />} />
        <Route path="/apps" element={<Applications />} />
        <Route path="/trading" element={<Trading />} />
        <Route path="/verticals" element={<Verticals />} />
        <Route path="/tenants" element={<Tenants />} />
        <Route path="/billing" element={<Billing />} />
      </Routes>
    </Layout>
  )
}
