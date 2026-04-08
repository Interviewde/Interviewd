import { Link, Outlet, useLocation } from "react-router-dom";

const NAV = [
  { to: "/", label: "Dashboard" },
  { to: "/setup", label: "New Interview" },
  { to: "/practice", label: "Practice" },
  { to: "/sessions", label: "History" },
];

export default function Layout() {
  const { pathname } = useLocation();

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
          <Link to="/" className="text-brand-600 font-bold text-lg tracking-tight">
            Interviewd
          </Link>
          <nav className="flex gap-6">
            {NAV.map(({ to, label }) => (
              <Link
                key={to}
                to={to}
                className={`text-sm font-medium transition-colors ${
                  pathname === to
                    ? "text-brand-600"
                    : "text-gray-500 hover:text-gray-800"
                }`}
              >
                {label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-8">
        <Outlet />
      </main>
      <footer className="text-center text-xs text-gray-400 py-4">
        Interviewd — open-source voice mock interview agent
      </footer>
    </div>
  );
}
