import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, Input, Label } from "@/components/ui/primitives";
import { Sparkles } from "lucide-react";

export function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [needsSetup, setNeedsSetup] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api<{ needs_setup: boolean }>("/api/auth/status")
      .then((s) => {
        if (s.needs_setup) navigate("/setup");
        setNeedsSetup(s.needs_setup);
      })
      .catch(() => undefined);
  }, [navigate]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const res = await api<{ access_token: string; setup_complete: boolean }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setToken(res.access_token);
      navigate(res.setup_complete ? "/" : "/setup");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    }
  }

  return (
    <div className="min-h-screen grid place-items-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="h-6 w-6 text-primary" />
            <CardTitle>Sign in to FinAgent</CardTitle>
          </div>
          <p className="text-sm text-muted-foreground">Your data never leaves your network.</p>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={onSubmit}>
            <div className="space-y-2">
              <Label htmlFor="user">Username</Label>
              <Input id="user" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pass">Password</Label>
              <Input id="pass" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
            </div>
            {error && <p className="text-sm text-down">{error}</p>}
            <Button className="w-full" type="submit">Sign in</Button>
            {needsSetup && (
              <Button type="button" variant="outline" className="w-full" onClick={() => navigate("/setup")}>
                Run setup wizard
              </Button>
            )}
          </form>
        </CardContent>
      </Card>
    </div>
  );
}