import { Link, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AuditsProvider } from "./lib/audits";
import { useDocumentTitle } from "./lib/hooks";
import { Compare } from "./pages/Compare";
import { Dashboard } from "./pages/Dashboard";
import { History } from "./pages/History";
import { ImportPage } from "./pages/Import";
import { Issues } from "./pages/Issues";
import { Products } from "./pages/Products";
import { Rules } from "./pages/Rules";

function NotFound() {
  useDocumentTitle("Page introuvable");
  return (
    <div className="panel state">
      <h1>Cette page n'existe pas</h1>
      <p>L'adresse est peut-être incomplète.</p>
      <div className="actions">
        <Link className="btn btn-primary" to="/">
          Revenir au tableau de bord
        </Link>
      </div>
    </div>
  );
}

export function App() {
  return (
    <AuditsProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="issues" element={<Issues />} />
          <Route path="products" element={<Products />} />
          <Route path="compare" element={<Compare />} />
          <Route path="history" element={<History />} />
          <Route path="import" element={<ImportPage />} />
          <Route path="rules" element={<Rules />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </AuditsProvider>
  );
}
