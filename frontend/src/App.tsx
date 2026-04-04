import { createBrowserRouter, RouterProvider } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Setup from "./pages/Setup";
import Interview from "./pages/Interview";
import Report from "./pages/Report";
import Sessions from "./pages/Sessions";

const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "setup", element: <Setup /> },
      { path: "interview/:sessionId", element: <Interview /> },
      { path: "report/:sessionId", element: <Report /> },
      { path: "sessions", element: <Sessions /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
