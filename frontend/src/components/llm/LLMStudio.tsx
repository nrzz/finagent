import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  formatBytes,
  formatEta,
  streamOllamaPull,
  type PullProgressEvent,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardContent, CardHeader, CardTitle, Input, Label } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

export type ProviderMeta = {
  id: string;
  name: string;
  tagline: string;
  difficulty: string;
  cost: string;
  needs_api_key: boolean;
  needs_install: boolean;
  default_base_url: string | null;
  secret_name: string | null;
  recommended_for?: string;
  install: {
    title: string;
    steps: string[];
    links: { label: string; url: string }[];
  };
  presets: {
    id: string;
    label: string;
    model: string;
    tier: string;
    ram: string;
    pull?: string;
    recommended_for?: string;
    note?: string;
  }[];
};

export type LLMProfile = {
  id: string;
  name: string;
  provider: string;
  model: string;
  base_url?: string | null;
  api_key_name?: string | null;
  tool_mode: string;
  timeout_s: number;
  enabled: boolean;
};

type LLMBundle = {
  profiles: LLMProfile[];
  active_profile_id: string | null;
  fallback_profile_id: string | null;
  chat_profile_id: string | null;
  analysis_profile_id: string | null;
};

type Props = {
  /** Compact mode for setup wizard */
  compact?: boolean;
  onActivated?: (profile: LLMProfile) => void;
};

const DIFFICULTY_COLOR: Record<string, string> = {
  easiest: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  easy: "border-sky-500/40 bg-sky-500/10 text-sky-300",
  advanced: "border-amber-500/40 bg-amber-500/10 text-amber-300",
};

export function LLMStudio({ compact = false, onActivated }: Props) {
  const [catalog, setCatalog] = useState<ProviderMeta[]>([]);
  const [bundle, setBundle] = useState<LLMBundle | null>(null);
  const [providerId, setProviderId] = useState("demo");
  const [name, setName] = useState("My LLM");
  const [model, setModel] = useState("demo");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [editId, setEditId] = useState<string | null>(null);
  const [detected, setDetected] = useState<string[]>([]);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [pullModel, setPullModel] = useState("qwen2.5:3b");
  const [pullProgress, setPullProgress] = useState<PullProgressEvent | null>(null);
  const pullAbort = useRef<AbortController | null>(null);
  const [loadedModels, setLoadedModels] = useState<string[]>([]);
  const [ollamaDetected, setOllamaDetected] = useState<{ online: boolean; models: string[] }>({
    online: false,
    models: [],
  });

  const provider = useMemo(
    () => catalog.find((p) => p.id === providerId) || null,
    [catalog, providerId],
  );

  const load = useCallback(async (preferActive = false) => {
    const res = await api<{
      settings: {
        llm: LLMBundle & { profiles: LLMProfile[] };
      };
      catalog: ProviderMeta[];
    }>("/api/settings");
    setCatalog(res.catalog || []);
    const llm = res.settings.llm;
    setBundle({
      profiles: llm.profiles || [],
      active_profile_id: llm.active_profile_id,
      fallback_profile_id: llm.fallback_profile_id,
      chat_profile_id: llm.chat_profile_id,
      analysis_profile_id: llm.analysis_profile_id,
    });
    if (preferActive) {
      const active =
        (llm.profiles || []).find((p) => p.id === llm.active_profile_id) || llm.profiles?.[0];
      if (active) {
        setProviderId(active.provider);
        setName(active.name);
        setModel(active.model);
        setBaseUrl(active.base_url || "");
        setEditId(active.id);
      }
    }
  }, []);

  useEffect(() => {
    load(true).catch((e) => setStatus(e instanceof Error ? e.message : "Failed to load"));
  }, [load]);

  // Silent Ollama auto-detect on mount (wizard + settings share this component)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api<{ ok: boolean; message?: string; models?: string[] }>(
          "/api/settings/llm/probe",
          {
            method: "POST",
            body: JSON.stringify({
              provider: "ollama",
              base_url: "http://127.0.0.1:11434",
            }),
          },
        );
        if (cancelled) return;
        const models = res.models || [];
        setOllamaDetected({ online: !!res.ok, models });
        if (res.ok && models.length) {
          setDetected((prev) => (prev.length ? prev : models));
        }
      } catch {
        if (!cancelled) setOllamaDetected({ online: false, models: [] });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  function selectProvider(id: string) {
    const meta = catalog.find((p) => p.id === id);
    setProviderId(id);
    setEditId(null);
    setApiKey("");
    setStatus("");
    if (!meta) return;
    setName(meta.name);
    setBaseUrl(meta.default_base_url || "");
    if (id === "ollama" && ollamaDetected.online && ollamaDetected.models.length) {
      setDetected(ollamaDetected.models);
      const preferred =
        ollamaDetected.models.find((m) => m.includes("qwen2.5:7b")) ||
        ollamaDetected.models.find((m) => m.includes("7b")) ||
        ollamaDetected.models.find((m) => m.includes("qwen2.5:3b")) ||
        ollamaDetected.models.find((m) => m.includes("3b")) ||
        ollamaDetected.models[0];
      setModel(preferred);
      setPullModel("qwen2.5:7b");
      setStatus(
        `Detected · ${ollamaDetected.models.length} installed. Click a catalog model to install & activate in one step.`,
      );
      return;
    }
    setDetected(id === "ollama" ? ollamaDetected.models : []);
    const preset = meta.presets[0];
    setModel(preset?.model || (id === "demo" ? "demo" : ""));
    if (preset?.pull) setPullModel(preset.pull);
    if (id === "ollama" && !ollamaDetected.online) {
      setStatus("Ollama not detected — install from ollama.com, then click a model to auto-install.");
    }
  }

  async function ensureDemoFallback(profiles: LLMProfile[], fallbackId: string | null) {
    if (fallbackId) return;
    const demo = profiles.find((p) => p.provider === "demo");
    if (!demo) return;
    try {
      const res = await api<{ settings: { llm: LLMBundle & { profiles: LLMProfile[] } } }>(
        "/api/settings/llm/activate",
        { method: "POST", body: JSON.stringify({ profile_id: demo.id, role: "fallback" }) },
      );
      const llm = res.settings.llm;
      setBundle({
        profiles: llm.profiles,
        active_profile_id: llm.active_profile_id,
        fallback_profile_id: llm.fallback_profile_id,
        chat_profile_id: llm.chat_profile_id,
        analysis_profile_id: llm.analysis_profile_id,
      });
    } catch {
      /* non-fatal */
    }
  }

  async function saveAndActivate(
    makeActive = true,
    overrides?: { model?: string; name?: string },
  ): Promise<LLMProfile | null> {
    setBusy("save");
    setStatus("Saving profile…");
    const modelToSave = overrides?.model ?? model;
    const nameToSave = overrides?.name ?? name;
    try {
      const res = await api<{
        ok: boolean;
        profile: LLMProfile;
        settings: { llm: LLMBundle & { profiles: LLMProfile[] } };
      }>("/api/settings/llm/profiles", {
        method: "POST",
        body: JSON.stringify({
          id: editId,
          name: nameToSave || provider?.name || "LLM",
          provider: providerId,
          model: providerId === "demo" ? "demo" : modelToSave,
          base_url: baseUrl || null,
          api_key_name: provider?.secret_name || null,
          api_key_value: apiKey || null,
          tool_mode: "auto",
          make_active: makeActive,
          make_fallback: false,
        }),
      });
      setEditId(res.profile.id);
      setApiKey("");
      if (overrides?.model) setModel(overrides.model);
      if (overrides?.name) setName(overrides.name);
      const llm = res.settings.llm;
      setBundle({
        profiles: llm.profiles,
        active_profile_id: llm.active_profile_id,
        fallback_profile_id: llm.fallback_profile_id,
        chat_profile_id: llm.chat_profile_id,
        analysis_profile_id: llm.analysis_profile_id,
      });
      if (makeActive && providerId !== "demo") {
        await ensureDemoFallback(llm.profiles, llm.fallback_profile_id);
      }
      setStatus(makeActive ? `Active: ${res.profile.name} (${res.profile.model})` : `Saved ${res.profile.name}`);
      onActivated?.(res.profile);
      return res.profile;
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Save failed");
      return null;
    } finally {
      setBusy(null);
    }
  }

  // Re-attach to an in-flight Ollama pull after refresh / navigation
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api<{
          active?: PullProgressEvent | null;
        }>("/api/settings/llm/ollama/pull/status");
        if (cancelled || !res.active?.running) return;
        const m = res.active.model;
        setProviderId("ollama");
        setPullModel(m);
        setPullProgress(res.active);
        setBusy("pull");
        setStatus(`Reconnected to install of ${m}`);
        const ac = new AbortController();
        pullAbort.current = ac;
        const last = await streamOllamaPull(
          m,
          baseUrl || "http://127.0.0.1:11434",
          (ev) => {
            if (!cancelled) setPullProgress(ev);
          },
          ac.signal,
        );
        if (cancelled) return;
        setPullProgress(last);
        if (last.phase === "success") {
          setModel(m);
          setDetected((prev) => (prev.includes(m) ? prev : [...prev, m]));
          setStatus(`Installed ${m}. Activating…`);
          await saveAndActivate(true, { model: m, name: `Ollama · ${m}` });
        } else if (last.phase === "failed") {
          setStatus(last.error || "Install failed");
        }
      } catch {
        /* no active pull */
      } finally {
        if (!cancelled) {
          setBusy(null);
          pullAbort.current = null;
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // intentionally once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refreshLoaded = useCallback(async () => {
    try {
      const res = await api<{ loaded?: { name: string }[] }>(
        `/api/settings/llm/ollama/ps?base_url=${encodeURIComponent(baseUrl || "http://127.0.0.1:11434")}`,
      );
      setLoadedModels((res.loaded || []).map((m) => m.name));
    } catch {
      setLoadedModels([]);
    }
  }, [baseUrl]);

  useEffect(() => {
    if (providerId === "ollama") void refreshLoaded();
  }, [providerId, refreshLoaded]);

  /** Cancel any install, activate model, unload other models from RAM (only one resident). */
  async function switchToInstalled(installedModel: string, label?: string) {
    const activePull =
      pullProgress &&
      !["success", "failed", "cancelled"].includes(pullProgress.phase)
        ? pullProgress.model
        : null;
    if (activePull && activePull !== installedModel) {
      await cancelPull();
    }
    setProviderId("ollama");
    setModel(installedModel);
    setPullModel(installedModel);
    const nice = label || `Ollama · ${installedModel}`;
    setName(nice);
    setPullProgress(null);
    setStatus(`Switching to ${installedModel} — unloading other models from RAM…`);
    await saveAndActivate(true, { model: installedModel, name: nice });
    try {
      const ex = await api<{ message?: string; unloaded?: string[]; loaded_now?: string[] }>(
        "/api/settings/llm/ollama/exclusive",
        {
          method: "POST",
          body: JSON.stringify({
            model: installedModel,
            base_url: baseUrl || "http://127.0.0.1:11434",
            warm: false,
          }),
        },
      );
      setLoadedModels(ex.loaded_now || [installedModel]);
      setStatus(
        ex.message ||
          `Active: ${installedModel}. Other Ollama models unloaded so your PC stays responsive.`,
      );
    } catch {
      setStatus(`Active: ${installedModel}. (Could not unload others — is Ollama running?)`);
    }
    await refreshLoaded();
  }

  async function cancelPull() {
    const m = pullProgress?.model || pullModel || "*";
    try {
      await api("/api/settings/llm/ollama/pull/cancel", {
        method: "POST",
        body: JSON.stringify({ model: m === "*" ? "*" : m, base_url: baseUrl || null }),
      });
    } catch {
      /* ignore */
    }
    pullAbort.current?.abort();
    setPullProgress((p) =>
      p ? { ...p, phase: "cancelled", error: "Cancelled by user", running: false } : p,
    );
    setBusy(null);
    setStatus("Install cancelled");
  }

  /** One-click: pull if needed, then save & activate — only one install at a time. */
  async function installAndActivate(targetModel: string, label: string, opts?: { replace?: boolean }) {
    const isHuge = /70b|72b|405b|120b/i.test(targetModel);
    if (isHuge && !window.confirm(
      `${label} is a large model (${targetModel}). It needs substantial RAM/VRAM and a multi‑GB download. Continue?`,
    )) {
      return;
    }
    const runningOther =
      pullProgress &&
      pullProgress.running !== false &&
      !["success", "failed", "cancelled"].includes(pullProgress.phase) &&
      pullProgress.model !== targetModel;
    let replace = opts?.replace ?? false;
    if (runningOther && !replace) {
      const ok = window.confirm(
        `Only one install at a time.\n\n“${pullProgress?.model}” is installing.\nCancel it and install “${targetModel}” instead?\n\nTip: click an Installed model to switch without downloading.`,
      );
      if (!ok) return;
      replace = true;
      await cancelPull();
    }

    setBusy("pull");
    setPullModel(targetModel);
    setModel(targetModel);
    setName(label);
    setPullProgress({
      model: targetModel,
      phase: "starting",
      percent: null,
      completed_bytes: 0,
      total_bytes: 0,
      speed_bps: 0,
      eta_s: null,
      status: "Starting…",
    });
    setStatus(`Installing ${label}… (only one install runs at a time)`);
    const ac = new AbortController();
    pullAbort.current = ac;
    try {
      const last = await streamOllamaPull(
        targetModel,
        baseUrl || null,
        (ev) => {
          setPullProgress(ev);
          if (ev.status === "already installed") {
            setStatus(`${label} already installed — activating…`);
          }
        },
        ac.signal,
        { replace },
      );
      setPullProgress(last);
      if (last.phase === "cancelled") {
        setStatus("Install cancelled");
        return;
      }
      if (last.phase !== "success") {
        setStatus(
          last.error ||
            "Install failed. Is Ollama running? Open ollama.com/download then retry.",
        );
        return;
      }
      const installed = last.model || targetModel;
      setModel(installed);
      try {
        const probeRes = await api<{ ok: boolean; models?: string[] }>("/api/settings/llm/probe", {
          method: "POST",
          body: JSON.stringify({
            provider: "ollama",
            base_url: baseUrl || "http://127.0.0.1:11434",
          }),
        });
        const models = probeRes.models || [];
        setDetected(models);
        setOllamaDetected({ online: !!probeRes.ok, models });
      } catch {
        setDetected((prev) => (prev.includes(installed) ? prev : [...prev, installed]));
      }
      setStatus(
        last.status === "already installed"
          ? `Already installed — activating ${installed}`
          : `Installed ${installed}. Activating…`,
      );
      await saveAndActivate(true, { model: installed, name: label });
      setPullProgress(null);
    } catch (e) {
      if ((e as Error).name === "AbortError") {
        setStatus("Install cancelled");
      } else {
        const msg = e instanceof Error ? e.message : "Install failed";
        if (msg.includes("Only one install") || msg.includes("409")) {
          setStatus(msg);
        } else {
          setStatus(msg);
        }
      }
    } finally {
      setBusy(null);
      pullAbort.current = null;
    }
  }

  async function selectPreset(preset: ProviderMeta["presets"][0]) {
    if (providerId === "ollama") {
      const pullName = preset.pull || preset.model;
      const installed = detected.find(
        (m) => m === preset.model || m === pullName || m.startsWith(`${preset.model}`) || m.startsWith(pullName),
      );
      if (installed) {
        await switchToInstalled(installed, preset.label);
        return;
      }
      await installAndActivate(pullName, preset.label);
      return;
    }
    setModel(preset.model);
    if (preset.pull) setPullModel(preset.pull);
  }

  function loadProfile(p: LLMProfile) {
    setEditId(p.id);
    setProviderId(p.provider);
    setName(p.name);
    setModel(p.model);
    setBaseUrl(p.base_url || "");
    setApiKey("");
    setStatus(`Editing “${p.name}”`);
  }

  async function probe() {
    setBusy("probe");
    setStatus("Checking provider…");
    try {
      const res = await api<{
        ok: boolean;
        message?: string;
        models?: string[];
      }>("/api/settings/llm/probe", {
        method: "POST",
        body: JSON.stringify({
          provider: providerId,
          base_url: baseUrl || null,
          api_key_name: provider?.secret_name || null,
        }),
      });
      setDetected(res.models || []);
      setStatus(res.ok ? res.message || "Online" : res.message || "Offline");
      if (res.models?.[0] && !model) setModel(res.models[0]);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Probe failed");
    } finally {
      setBusy(null);
    }
  }

  async function pull() {
    await installAndActivate(pullModel, `Ollama · ${pullModel}`);
  }

  async function testCurrent() {
    setBusy("test");
    setStatus("Testing…");
    try {
      const saved = await saveAndActivate(true);
      const pid = saved?.id;
      const path = pid ? `/api/settings/llm/test/${pid}` : "/api/settings/llm/test";
      const res = await api<{ ok: boolean; sample?: string; error?: string; tool_mode?: string }>(
        path,
        { method: "POST" },
      );
      setStatus(
        res.ok
          ? `Connected · tool_mode=${res.tool_mode} · ${res.sample || "ok"}`
          : `Failed: ${res.error}`,
      );
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Test failed");
    } finally {
      setBusy(null);
    }
  }

  async function setRole(profileId: string, role: "active" | "fallback" | "chat" | "analysis") {
    setBusy(`role-${role}`);
    try {
      const res = await api<{ settings: { llm: LLMBundle & { profiles: LLMProfile[] } } }>(
        "/api/settings/llm/activate",
        { method: "POST", body: JSON.stringify({ profile_id: profileId, role }) },
      );
      const llm = res.settings.llm;
      setBundle({
        profiles: llm.profiles,
        active_profile_id: llm.active_profile_id,
        fallback_profile_id: llm.fallback_profile_id,
        chat_profile_id: llm.chat_profile_id,
        analysis_profile_id: llm.analysis_profile_id,
      });
      setStatus(`Set ${role} → ${profileId}`);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(null);
    }
  }

  async function removeProfile(id: string) {
    if (!confirm("Remove this LLM profile?")) return;
    setBusy("delete");
    try {
      await api(`/api/settings/llm/profiles/${id}`, { method: "DELETE" });
      setEditId(null);
      await load();
      setStatus("Profile removed");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setBusy(null);
    }
  }

  if (!bundle) {
    return <p className="text-sm text-muted-foreground">Loading AI studio…</p>;
  }

  return (
    <div className={cn("space-y-5", compact && "space-y-4")}>
      {!compact && (
        <div>
          <h2 className="text-xl font-semibold tracking-tight">AI Studio</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Add local or cloud models in the UI — install guides, detect, pull, test, and activate.
            No YAML or env files.
          </p>
        </div>
      )}

      {/* Provider gallery */}
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {catalog.map((p) => {
          const selected = providerId === p.id;
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => selectProvider(p.id)}
              className={cn(
                "text-left rounded-xl border p-3 transition-all",
                "hover:border-primary/50 hover:bg-accent/40",
                selected ? "border-primary bg-primary/10 ring-1 ring-primary/40" : "border-border bg-card/40",
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-medium text-sm">{p.name}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">{p.tagline}</div>
                </div>
                <span
                  className={cn(
                    "shrink-0 text-[10px] uppercase tracking-wide rounded-md border px-1.5 py-0.5",
                    DIFFICULTY_COLOR[p.difficulty] || DIFFICULTY_COLOR.easy,
                  )}
                >
                  {p.difficulty}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <Badge className="text-[10px] font-normal">{p.cost}</Badge>
                {p.recommended_for === "finance" && (
                  <Badge className="text-[10px] font-normal border-emerald-500/40 text-emerald-300">
                    Best for finance
                  </Badge>
                )}
                {p.id === "ollama" && ollamaDetected.online && (
                  <Badge className="text-[10px] font-normal border-sky-500/40 text-sky-300">
                    Detected · {ollamaDetected.models.length} model
                    {ollamaDetected.models.length === 1 ? "" : "s"}
                  </Badge>
                )}
                {p.needs_install && !(p.id === "ollama" && ollamaDetected.online) && (
                  <Badge className="text-[10px] font-normal">Install once</Badge>
                )}
                {p.needs_api_key && <Badge className="text-[10px] font-normal">API key</Badge>}
                {!p.needs_install && !p.needs_api_key && (
                  <Badge className="text-[10px] font-normal border-emerald-500/30">Ready now</Badge>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {provider && (
        <Card className="overflow-hidden">
          <CardHeader className="pb-3 bg-gradient-to-br from-sky-500/10 via-transparent to-transparent">
            <CardTitle className="text-base">{provider.install.title}</CardTitle>
            <p className="text-xs text-muted-foreground">{provider.tagline}</p>
          </CardHeader>
          <CardContent className="space-y-4">
            <ol className="space-y-2 text-sm text-muted-foreground list-decimal pl-4">
              {provider.install.steps.map((step) => (
                <li key={step} className="leading-relaxed">
                  {step}
                </li>
              ))}
            </ol>
            {provider.install.links.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {provider.install.links.map((link) => (
                  <a
                    key={link.url}
                    href={link.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs font-medium text-primary underline-offset-4 hover:underline"
                  >
                    {link.label} ↗
                  </a>
                ))}
              </div>
            )}

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label>Profile name</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Home Ollama" />
              </div>
              {provider.needs_api_key && (
                <div className="space-y-1">
                  <Label>API key (encrypted on save)</Label>
                  <Input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder={provider.secret_name || "sk-…"}
                    autoComplete="off"
                  />
                </div>
              )}
              {(provider.needs_install || provider.id === "openai-compatible" || provider.id === "ollama") && (
                <div className="space-y-1 sm:col-span-2">
                  <Label>Base URL</Label>
                  <Input
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    placeholder={provider.default_base_url || ""}
                  />
                </div>
              )}
            </div>

            {provider.id === "ollama" && detected.length > 0 && (
              <div className="space-y-2">
                <Label>Installed — only one stays in RAM</Label>
                <p className="text-xs text-muted-foreground">
                  Click to switch. FinAgent unloads other Ollama models from memory so your PC does not
                  slow down. Downloaded files stay on disk.
                </p>
                {loadedModels.length > 1 && (
                  <p className="text-xs text-amber-200/90">
                    {loadedModels.length} models currently loaded in RAM — switch or click any below to
                    free memory.
                  </p>
                )}
                <div className="flex flex-wrap gap-2">
                  {detected.map((m) => {
                    const isActive =
                      bundle?.active_profile_id &&
                      bundle.profiles.find((p) => p.id === bundle.active_profile_id)?.model === m;
                    const inRam = loadedModels.some(
                      (l) => l === m || l.startsWith(m) || m.startsWith(l.split(":")[0]),
                    );
                    return (
                    <button
                      key={m}
                      type="button"
                      disabled={busy === "save"}
                      onClick={() => void switchToInstalled(m)}
                      className={cn(
                        "rounded-lg border px-3 py-2 text-left text-xs transition-colors disabled:opacity-50",
                        isActive || model === m
                          ? "border-primary bg-primary/15"
                          : "border-border hover:bg-accent/50",
                      )}
                    >
                      <div className="font-medium flex items-center gap-1.5 flex-wrap">
                        {m}
                        {isActive && (
                          <span className="text-[9px] uppercase tracking-wide text-emerald-300 border border-emerald-500/40 rounded px-1">
                            Active
                          </span>
                        )}
                        {inRam && (
                          <span className="text-[9px] uppercase tracking-wide text-sky-200 border border-sky-500/40 rounded px-1">
                            In RAM
                          </span>
                        )}
                      </div>
                      <div className="text-muted-foreground mt-0.5">
                        {isActive ? "In use · others unloaded" : "Click to run only this"}
                      </div>
                    </button>
                    );
                  })}
                </div>
              </div>
            )}

            {provider.presets.length > 0 && provider.id !== "demo" && (
              <div className="space-y-2">
                <Label>
                  {provider.id === "ollama"
                    ? "Catalog — one install at a time (or switch to Installed above)"
                    : "Model presets"}
                </Label>
                <div className="flex flex-wrap gap-2">
                  {provider.presets.map((preset) => {
                    const pullName = preset.pull || preset.model;
                    const installed =
                      provider.id !== "ollama" ||
                      detected.some(
                        (m) =>
                          m === preset.model ||
                          m === pullName ||
                          m.startsWith(`${preset.model}`) ||
                          m.startsWith(pullName),
                      );
                    return (
                    <button
                      key={preset.id}
                      type="button"
                      disabled={
                        busy === "save" ||
                        busy === "test" ||
                        busy === "probe" ||
                        (busy === "pull" && provider.id !== "ollama")
                      }
                      onClick={() => void selectPreset(preset)}
                      className={cn(
                        "rounded-lg border px-3 py-2 text-left text-xs transition-colors disabled:opacity-50",
                        model === preset.model || model === pullName
                          ? "border-primary bg-primary/15"
                          : "border-border hover:bg-accent/50",
                      )}
                    >
                      <div className="font-medium flex items-center gap-1.5 flex-wrap">
                        {preset.label}
                        {provider.id === "ollama" && (
                          <span
                            className={cn(
                              "text-[9px] uppercase tracking-wide rounded px-1 border",
                              installed
                                ? "text-emerald-300 border-emerald-500/40"
                                : "text-sky-200 border-sky-500/40",
                            )}
                          >
                            {installed ? "Ready" : "Click to install"}
                          </span>
                        )}
                        {preset.recommended_for === "finance" && (
                          <span className="text-[9px] uppercase tracking-wide text-emerald-300 border border-emerald-500/40 rounded px-1">
                            Finance
                          </span>
                        )}
                      </div>
                      <div className="text-muted-foreground mt-0.5">
                        <span
                          className={cn(
                            preset.tier === "flagship" && "text-amber-200",
                            preset.tier === "high-end" && "text-sky-200",
                          )}
                        >
                          {preset.tier}
                        </span>
                        {" · "}
                        {preset.ram}
                        {provider.id === "ollama" && !installed
                          ? " · downloads then activates"
                          : ""}
                      </div>
                      {preset.note && (
                        <div className="text-muted-foreground/80 mt-1 leading-snug">{preset.note}</div>
                      )}
                    </button>
                    );
                  })}
                </div>
              </div>
            )}

            {provider.id !== "demo" && (
              <div className="space-y-1">
                <Label>Model id</Label>
                <Input
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  list="llm-detected-models"
                  placeholder="model name"
                />
                <datalist id="llm-detected-models">
                  {detected.map((m) => (
                    <option key={m} value={m} />
                  ))}
                </datalist>
                {provider.id === "ollama" && pullProgress && (
                  <div className="rounded-lg border border-border bg-muted/30 p-3 space-y-2">
                    <div className="flex items-center justify-between gap-2 text-xs">
                      <span className="font-medium">
                        Installing {pullProgress.model}{" "}
                        <span className="text-muted-foreground capitalize">
                          · {pullProgress.phase}
                        </span>
                        <span className="ml-1 text-muted-foreground">(only one at a time)</span>
                      </span>
                      {pullProgress.phase !== "success" &&
                        pullProgress.phase !== "failed" &&
                        pullProgress.phase !== "cancelled" && (
                          <Button
                            type="button"
                            variant="outline"
                            className="h-7 px-2 text-xs"
                            onClick={() => void cancelPull()}
                          >
                            Cancel
                          </Button>
                        )}
                    </div>
                    {detected.length > 0 &&
                      pullProgress.phase !== "success" &&
                      pullProgress.phase !== "failed" &&
                      pullProgress.phase !== "cancelled" && (
                        <div className="rounded-md border border-dashed border-border/80 p-2 space-y-1.5">
                          <p className="text-[11px] text-muted-foreground">
                            Switch to an installed model now (stops this download):
                          </p>
                          <div className="flex flex-wrap gap-1.5">
                            {detected.map((m) => (
                              <button
                                key={m}
                                type="button"
                                className="rounded border border-border px-2 py-1 text-[11px] hover:bg-accent/50"
                                onClick={() => void switchToInstalled(m)}
                              >
                                Use {m}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    {pullProgress.total_bytes > 0 && pullProgress.percent != null ? (
                      <>
                        <div className="h-2 w-full overflow-hidden rounded-full bg-border">
                          <div
                            className="h-full rounded-full bg-primary transition-[width] duration-300"
                            style={{ width: `${Math.min(100, Math.max(0, pullProgress.percent))}%` }}
                          />
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {pullProgress.percent.toFixed(1)}% ·{" "}
                          {formatBytes(pullProgress.completed_bytes)} /{" "}
                          {formatBytes(pullProgress.total_bytes)}
                          {pullProgress.speed_bps > 0 && (
                            <> · {formatBytes(pullProgress.speed_bps)}/s</>
                          )}
                          {pullProgress.eta_s != null && (
                            <> · {formatEta(pullProgress.eta_s)} left</>
                          )}
                        </p>
                      </>
                    ) : (
                      <div className="space-y-1">
                        <div className="h-2 w-full overflow-hidden rounded-full bg-border">
                          <div className="h-full w-1/3 animate-pulse rounded-full bg-primary/70" />
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {pullProgress.status || "Preparing download…"}
                        </p>
                      </div>
                    )}
                    {pullProgress.error && (
                      <p className="text-xs text-amber-200/90">{pullProgress.error}</p>
                    )}
                    {(pullProgress.phase === "failed" ||
                      pullProgress.phase === "cancelled") && (
                      <Button
                        type="button"
                        variant="secondary"
                        className="h-8 text-xs"
                        onClick={() =>
                          void installAndActivate(pullProgress.model, name || pullProgress.model)
                        }
                      >
                        Retry
                      </Button>
                    )}
                  </div>
                )}
              </div>
            )}

            {provider.id === "ollama" && (
              <div className="rounded-lg border border-dashed border-border p-3 space-y-2 bg-muted/20">
                <Label className="text-xs uppercase tracking-wide text-muted-foreground">
                  Or type a model name (install + activate)
                </Label>
                <div className="flex flex-col sm:flex-row gap-2">
                  <Input value={pullModel} onChange={(e) => setPullModel(e.target.value)} />
                  <Button variant="secondary" onClick={() => void pull()} disabled={busy !== null}>
                    {busy === "pull" ? "Installing…" : "Install & activate"}
                  </Button>
                </div>
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              {provider.id !== "demo" && (
                <Button variant="secondary" onClick={probe} disabled={busy !== null}>
                  {busy === "probe" ? "Detecting…" : "Detect"}
                </Button>
              )}
              <Button variant="secondary" onClick={testCurrent} disabled={busy !== null}>
                {busy === "test" ? "Testing…" : "Test"}
              </Button>
              <Button onClick={() => saveAndActivate(true)} disabled={busy !== null}>
                {busy === "save" ? "Saving…" : "Save & activate"}
              </Button>
              <Button variant="outline" onClick={() => saveAndActivate(false)} disabled={busy !== null}>
                Save only
              </Button>
            </div>

            {status && (
              <p
                className={cn(
                  "text-sm font-mono rounded-md border px-3 py-2",
                  status.toLowerCase().includes("fail") || status.toLowerCase().includes("offline")
                    ? "border-red-500/30 bg-red-500/10 text-red-200"
                    : "border-border bg-muted/30 text-muted-foreground",
                )}
              >
                {status}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Saved profiles */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Saved profiles</CardTitle>
          <p className="text-xs text-muted-foreground">
            Active is used by default. Fallback kicks in if Active fails. Optionally route Chat vs Analysis.
          </p>
        </CardHeader>
        <CardContent className="space-y-2">
          {bundle.profiles.length === 0 && (
            <p className="text-sm text-muted-foreground">No profiles yet — pick a provider above.</p>
          )}
          {bundle.profiles.map((p) => {
            const roles: string[] = [];
            if (p.id === bundle.active_profile_id) roles.push("Active");
            if (p.id === bundle.fallback_profile_id) roles.push("Fallback");
            if (p.id === bundle.chat_profile_id) roles.push("Chat");
            if (p.id === bundle.analysis_profile_id) roles.push("Analysis");
            return (
              <div
                key={p.id}
                className={cn(
                  "flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between",
                  p.id === bundle.active_profile_id ? "border-primary/50 bg-primary/5" : "border-border",
                )}
              >
                <button type="button" className="text-left min-w-0" onClick={() => loadProfile(p)}>
                  <div className="font-medium text-sm truncate">{p.name}</div>
                  <div className="text-xs text-muted-foreground truncate">
                    {p.provider} · {p.model}
                  </div>
                  {roles.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {roles.map((r) => (
                        <Badge key={r} className="text-[10px]">
                          {r}
                        </Badge>
                      ))}
                    </div>
                  )}
                </button>
                {!compact && (
                  <div className="flex flex-wrap gap-1.5 shrink-0">
                    <Button size="sm" variant="secondary" onClick={() => setRole(p.id, "active")}>
                      Active
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setRole(p.id, "fallback")}>
                      Fallback
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setRole(p.id, "chat")}>
                      Chat
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setRole(p.id, "analysis")}>
                      Analysis
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => removeProfile(p.id)}>
                      Remove
                    </Button>
                  </div>
                )}
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}
