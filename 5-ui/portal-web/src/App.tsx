import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Overview from './pages/Overview'
import Ingestion from './pages/Ingestion'
import Stream from './pages/Stream'
import AIAgents from './pages/AIAgents'
import Applications from './pages/Applications'
import Tenants from './pages/Tenants'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/ingestion" element={<Ingestion />} />
        <Route path="/stream" element={<Stream />} />
        <Route path="/ai" element={<AIAgents />} />
        <Route path="/apps" element={<Applications />} />
        <Route path="/tenants" element={<Tenants />} />
      </Routes>
    </Layout>
  )
}
