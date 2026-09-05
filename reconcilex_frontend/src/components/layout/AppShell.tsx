import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'

export function AppShell() {
  return (
    <div className="min-h-screen bg-canvas">
      <Sidebar />
      <div className="md:pl-60">
        <Outlet />
      </div>
    </div>
  )
}
