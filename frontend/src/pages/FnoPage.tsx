import { Navigate, useSearchParams } from "react-router-dom";

/** F&O redirects into the Trading Desk F&O mode. */
export function FnoPage() {
  const [params] = useSearchParams();
  const next = new URLSearchParams(params);
  next.set("mode", "fno");
  return <Navigate to={`/trading?${next}`} replace />;
}
