import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import NewResearch from "./pages/NewResearch";
import JobProgress from "./pages/JobProgress";
import Results from "./pages/Results";
import RecordDetail from "./pages/RecordDetail";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/research/new" element={<NewResearch />} />
          <Route path="/research/:id" element={<JobProgress />} />
          <Route path="/results/:id" element={<Results />} />
          <Route path="/results/:id/record/:resultId" element={<RecordDetail />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
