import { Navigate, useSearchParams } from "react-router-dom";

/** Markets redirects into the unified Trading Desk. */
export function MarketsPage() {
  const [params] = useSearchParams();
  const qs = params.toString();
  return <Navigate to={qs ? `/trading?${qs}` : "/trading"} replace />;
}
