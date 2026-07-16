import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import { getToken } from "@/lib/api";
import { LoginPage } from "@/pages/LoginPage";
import { SetupWizardPage } from "@/pages/SetupWizardPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { ChatPage } from "@/pages/ChatPage";
import { PortfolioPage } from "@/pages/PortfolioPage";
import { MarketsPage } from "@/pages/MarketsPage";
import { TradingDeskPage } from "@/pages/TradingDeskPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { FnoPage } from "@/pages/FnoPage";
import { AutomationPage } from "@/pages/AutomationPage";

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/setup" element={<SetupWizardPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<ChatPage />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="chat" element={<Navigate to="/" replace />} />
        <Route path="portfolio" element={<PortfolioPage />} />
        <Route path="markets" element={<MarketsPage />} />
        <Route path="trading" element={<TradingDeskPage />} />
        <Route path="fno" element={<FnoPage />} />
        <Route path="automation" element={<AutomationPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
