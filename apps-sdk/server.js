import { createServer } from "node:http";
import { readFileSync, existsSync } from "node:fs";
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// apps-sdk lives in: <workspace>/AdaptiveCAD/apps-sdk
// python venv lives in: <workspace>/.venv
const adaptiveCadRoot = path.resolve(__dirname, "..");
const workspaceRoot = path.resolve(adaptiveCadRoot, "..");

console.error(`[startup] __dirname=${__dirname}`);
console.error(`[startup] adaptiveCadRoot=${adaptiveCadRoot}`);
console.error(`[startup] workspaceRoot=${workspaceRoot}`);

const widgetHtml = readFileSync(path.join(__dirname, "public", "adaptivecad-widget.html"), "utf8");

const pythonFromVenv = path.join(workspaceRoot, ".venv", "Scripts", "python.exe");
const pythonExe = process.env.PYTHON && process.env.PYTHON.trim().length
  ? process.env.PYTHON.trim()
  : existsSync(pythonFromVenv)
    ? pythonFromVenv
    : "python";

const condaExeFromEnv = (process.env.ADAPTIVECAD_CONDA_EXE ?? process.env.CONDA_EXE ?? "").trim();
const condaExe = condaExeFromEnv && existsSync(condaExeFromEnv) ? condaExeFromEnv : "";
const condaEnvName = (process.env.ADAPTIVECAD_CONDA_ENV ?? "adaptivecad").trim() || "adaptivecad";

const bridgePath = path.join(__dirname, "adaptivecad_bridge.py");

const runJosephsonInputSchema = {
  size: z.number().int().min(8).max(256).default(48),
  steps: z.number().int().min(1).max(5000).default(400),
  s_target: z.number().min(0.05).max(0.95).default(0.5),
  seed: z.number().int().min(-1_000_000).max(1_000_000).default(0),
};

const runPrRelaxationInputSchema = {
  size: z.number().int().min(8).max(256).default(64),
  steps: z.number().int().min(1).max(5000).default(200),
  dt: z.number().min(0.001).max(2.0).default(0.15),
  diffusion: z.number().min(0.0).max(5.0).default(0.35),
  coupling: z.number().min(0.0).max(5.0).default(0.25),
  phase_dim: z.number().int().min(1).max(8).default(2),
  phase_space: z.enum(["unwrapped", "wrapped"]).default("unwrapped"),
  coupling_mode: z.enum(["none", "geom_target"]).default("geom_target"),
  seed: z.number().int().min(-1_000_000).max(1_000_000).default(0),
};

const runPrAndExportStlInputSchema = {
  size: z.number().int().min(8).max(256).default(32),
  steps: z.number().int().min(1).max(5000).default(100),
  dt: z.number().min(0.001).max(2.0).default(0.15),
  diffusion: z.number().min(0.0).max(5.0).default(0.35),
  coupling: z.number().min(0.0).max(5.0).default(0.25),
  phase_dim: z.number().int().min(1).max(8).default(2),
  phase_space: z.enum(["unwrapped", "wrapped"]).default("unwrapped"),
  coupling_mode: z.enum(["none", "geom_target"]).default("geom_target"),
  scale_xy: z.number().min(0.01).max(10.0).default(0.5),
  scale_z: z.number().min(0.01).max(10.0).default(2.0),
  seed: z.number().int().min(-1_000_000).max(1_000_000).default(0),
};

const runPrAndExportAmaInputSchema = {
  size: z.number().int().min(8).max(256).default(32),
  steps: z.number().int().min(1).max(5000).default(100),
  dt: z.number().min(0.001).max(2.0).default(0.15),
  diffusion: z.number().min(0.0).max(5.0).default(0.35),
  coupling: z.number().min(0.0).max(5.0).default(0.25),
  phase_dim: z.number().int().min(1).max(8).default(2),
  phase_space: z.enum(["unwrapped", "wrapped"]).default("unwrapped"),
  coupling_mode: z.enum(["none", "geom_target"]).default("geom_target"),
  scale_xy: z.number().min(0.01).max(10.0).default(0.5),
  scale_z: z.number().min(0.01).max(10.0).default(2.0),
  units: z.string().default("mm"),
  defl: z.number().min(0.001).max(10.0).default(0.05),
  seed: z.number().int().min(-1_000_000).max(1_000_000).default(0),
};

/** @type {{id: string, ok: boolean, params: any, result?: any, output?: string}[]} */
let runs = [];
let nextRunId = 1;

/** @type {{id: string, ok: boolean, params: any, result?: any, output?: string}[]} */
let prRuns = [];
let nextPrRunId = 1;

const replyWithRuns = (message) => ({
  content: message ? [{ type: "text", text: message }] : [],
  structuredContent: { runs, prRuns },
});

function spawnWithTimeout(command, args, opts, timeoutMs) {
  return new Promise((resolve) => {
    const child = spawn(command, args, opts);

    let stdout = "";
    let stderr = "";

    const killTimer = setTimeout(() => {
      try {
        child.kill();
      } catch {
        // ignore
      }
    }, timeoutMs);

    child.stdout?.on("data", (chunk) => {
      stdout += chunk.toString("utf8");
      if (stdout.length > 32_000) stdout = stdout.slice(-32_000);
    });

    child.stderr?.on("data", (chunk) => {
      stderr += chunk.toString("utf8");
      if (stderr.length > 32_000) stderr = stderr.slice(-32_000);
    });

    child.on("close", (code, signal) => {
      clearTimeout(killTimer);
      resolve({ code, signal, stdout, stderr });
    });
  });
}

function parseJsonLoose(text) {
  if (!text) return null;
  const trimmed = String(text).trim();
  try {
    return JSON.parse(trimmed);
  } catch {
    // Attempt to recover if stdout/stderr got mixed with warnings.
    const first = trimmed.indexOf("{");
    const last = trimmed.lastIndexOf("}");
    if (first >= 0 && last > first) {
      const candidate = trimmed.slice(first, last + 1);
      try {
        return JSON.parse(candidate);
      } catch {
        return null;
      }
    }
    return null;
  }
}

async function runJosephson(params) {
  const runId = `run-${nextRunId++}`;

  const argv = [
    bridgePath,
    "run_josephson",
    "--size",
    String(params.size),
    "--steps",
    String(params.steps),
    "--s-target",
    String(params.s_target),
    "--seed",
    String(params.seed),
  ];

  const env = {
    ...process.env,
    MPLBACKEND: "Agg",
  };

  const exec = await spawnWithTimeout(
    pythonExe,
    argv,
    {
      cwd: adaptiveCadRoot,
      env,
      windowsHide: true,
    },
    60_000
  );

  const output = [exec.stdout?.trim(), exec.stderr?.trim()].filter(Boolean).join("\n\n");

  if (exec.code !== 0) {
    runs = [
      {
        id: runId,
        ok: false,
        params,
        output: output || `Python failed (code ${exec.code ?? "?"}).`,
      },
      ...runs,
    ].slice(0, 20);

    return replyWithRuns(`Josephson run failed (${runId}).`);
  }

  let parsed;
  try {
    parsed = JSON.parse(exec.stdout);
  } catch (e) {
    runs = [
      {
        id: runId,
        ok: false,
        params,
        output: output || "Failed to parse JSON from Python bridge.",
      },
      ...runs,
    ].slice(0, 20);

    return replyWithRuns(`Josephson run produced invalid output (${runId}).`);
  }

  runs = [
    {
      id: runId,
      ok: true,
      params,
      result: parsed,
      output: "",
    },
    ...runs,
  ].slice(0, 20);

  return replyWithRuns(`Josephson run complete (${runId}).`);
}

async function runPrRelaxation(params) {
  const runId = `pr-${nextPrRunId++}`;

  const argv = [
    bridgePath,
    "run_pr_relaxation",
    "--size",
    String(params.size),
    "--steps",
    String(params.steps),
    "--dt",
    String(params.dt),
    "--diffusion",
    String(params.diffusion),
    "--coupling",
    String(params.coupling),
    "--coupling-mode",
    String(params.coupling_mode),
    "--phase-dim",
    String(params.phase_dim),
    "--phase-space",
    String(params.phase_space),
    "--seed",
    String(params.seed),
  ];

  const env = {
    ...process.env,
    MPLBACKEND: "Agg",
  };

  const exec = await spawnWithTimeout(
    pythonExe,
    argv,
    {
      cwd: adaptiveCadRoot,
      env,
      windowsHide: true,
    },
    60_000
  );

  const output = [exec.stdout?.trim(), exec.stderr?.trim()].filter(Boolean).join("\n\n");

  if (exec.code !== 0) {
    prRuns = [
      {
        id: runId,
        ok: false,
        params,
        output: output || `Python failed (code ${exec.code ?? "?"}).`,
      },
      ...prRuns,
    ].slice(0, 20);

    return replyWithRuns(`PR relaxation failed (${runId}).`);
  }

  let parsed;
  try {
    parsed = parseJsonLoose(exec.stdout);
    if (!parsed) throw new Error("parse failed");
  } catch (e) {
    prRuns = [
      {
        id: runId,
        ok: false,
        params,
        output: output || "Failed to parse JSON from Python bridge.",
      },
      ...prRuns,
    ].slice(0, 20);

    return replyWithRuns(`PR relaxation produced invalid output (${runId}).`);
  }

  prRuns = [
    {
      id: runId,
      ok: true,
      params,
      result: parsed,
      output: "",
    },
    ...prRuns,
  ].slice(0, 20);

  return replyWithRuns(`PR relaxation complete (${runId}).`);
}

async function runPrAndExportStl(params) {
  const runId = `pr-stl-${nextPrRunId++}`;

  const argv = [
    bridgePath,
    "run_pr_and_export_stl",
    "--size",
    String(params.size),
    "--steps",
    String(params.steps),
    "--dt",
    String(params.dt),
    "--diffusion",
    String(params.diffusion),
    "--coupling",
    String(params.coupling),
    "--coupling-mode",
    String(params.coupling_mode),
    "--phase-dim",
    String(params.phase_dim),
    "--phase-space",
    String(params.phase_space),
    "--scale-xy",
    String(params.scale_xy),
    "--scale-z",
    String(params.scale_z),
    "--seed",
    String(params.seed),
  ];

  const env = {
    ...process.env,
    MPLBACKEND: "Agg",
  };

  const exec = await spawnWithTimeout(
    pythonExe,
    argv,
    {
      cwd: adaptiveCadRoot,
      env,
      windowsHide: true,
    },
    60_000
  );

  const output = [exec.stdout?.trim(), exec.stderr?.trim()].filter(Boolean).join("\n\n");

  if (exec.code !== 0) {
    prRuns = [
      {
        id: runId,
        ok: false,
        params,
        output: output || `Python failed (code ${exec.code ?? "?"}).`,
      },
      ...prRuns,
    ].slice(0, 20);

    return replyWithRuns(`PR relaxation + STL export failed (${runId}).`);
  }

  let parsed;
  try {
    parsed = JSON.parse(exec.stdout);
  } catch (e) {
    prRuns = [
      {
        id: runId,
        ok: false,
        params,
        output: output || "Failed to parse JSON from Python bridge.",
      },
      ...prRuns,
    ].slice(0, 20);

    return replyWithRuns(`PR relaxation + STL export produced invalid output (${runId}).`);
  }

  prRuns = [
    {
      id: runId,
      ok: true,
      params,
      result: parsed,
      output: "",
    },
    ...prRuns,
  ].slice(0, 20);

  return replyWithRuns(`PR relaxation + STL export complete (${runId}).`);
}

async function runPrAndExportAma(params) {
  const runId = `pr-ama-${nextPrRunId++}`;

  const argv = [
    bridgePath,
    "run_pr_and_export_ama",
    "--size",
    String(params.size),
    "--steps",
    String(params.steps),
    "--dt",
    String(params.dt),
    "--diffusion",
    String(params.diffusion),
    "--coupling",
    String(params.coupling),
    "--coupling-mode",
    String(params.coupling_mode),
    "--phase-dim",
    String(params.phase_dim),
    "--phase-space",
    String(params.phase_space),
    "--scale-xy",
    String(params.scale_xy),
    "--scale-z",
    String(params.scale_z),
    "--units",
    String(params.units),
    "--defl",
    String(params.defl),
    "--seed",
    String(params.seed),
  ];

  const env = {
    ...process.env,
    MPLBACKEND: "Agg",
  };

  const command = condaExe || pythonExe;
  const args = condaExe
    ? ["run", "-n", condaEnvName, "python", ...argv]
    : argv;

  const exec = await spawnWithTimeout(
    command,
    args,
    {
      cwd: adaptiveCadRoot,
      env,
      windowsHide: true,
    },
    60_000
  );

  const output = [exec.stdout?.trim(), exec.stderr?.trim()].filter(Boolean).join("\n\n");

  if (exec.code !== 0) {
    prRuns = [
      {
        id: runId,
        ok: false,
        params,
        output:
          output ||
          (condaExe
            ? `Python failed (code ${exec.code ?? "?"}). (Tried conda env '${condaEnvName}'.)`
            : `Python failed (code ${exec.code ?? "?"}).`),
      },
      ...prRuns,
    ].slice(0, 20);

    return replyWithRuns(`PR relaxation + AMA export failed (${runId}).`);
  }

  let parsed;
  try {
    parsed = JSON.parse(exec.stdout);
  } catch (e) {
    prRuns = [
      {
        id: runId,
        ok: false,
        params,
        output:
          output ||
          (condaExe
            ? `Failed to parse JSON from Python bridge. (conda env '${condaEnvName}')`
            : "Failed to parse JSON from Python bridge."),
      },
      ...prRuns,
    ].slice(0, 20);

    return replyWithRuns(`PR relaxation + AMA export produced invalid output (${runId}).`);
  }

  prRuns = [
    {
      id: runId,
      ok: true,
      params,
      result: parsed,
      output: "",
    },
    ...prRuns,
  ].slice(0, 20);

  return replyWithRuns(`PR relaxation + AMA export complete (${runId}).`);
}

function createAdaptiveCadServer() {
  const server = new McpServer({ name: "adaptivecad-app", version: "0.1.0" });

  server.registerResource(
    "adaptivecad-widget",
    "ui://widget/adaptivecad.html",
    {},
    async () => ({
      contents: [
        {
          uri: "ui://widget/adaptivecad.html",
          mimeType: "text/html+skybridge",
          text: widgetHtml,
          _meta: { "openai/widgetPrefersBorder": true },
        },
      ],
    })
  );

  server.registerTool(
    "run_josephson",
    {
      title: "Run Josephson lattice (AdaptiveCAD)",
      description:
        "Runs AdaptiveCAD's adaptive Josephson lattice example headlessly and returns summary metrics.",
      inputSchema: runJosephsonInputSchema,
      _meta: {
        "openai/outputTemplate": "ui://widget/adaptivecad.html",
        "openai/toolInvocation/invoking": "Running Josephson lattice",
        "openai/toolInvocation/invoked": "Finished Josephson lattice",
      },
    },
    async (args) => {
      const size = Number(args?.size ?? 48);
      const steps = Number(args?.steps ?? 400);
      const s_target = Number(args?.s_target ?? 0.5);
      const seed = Number(args?.seed ?? 0);

      if (!Number.isFinite(size) || !Number.isFinite(steps) || !Number.isFinite(s_target)) {
        return replyWithRuns("Invalid parameters.");
      }

      return runJosephson({ size, steps, s_target, seed });
    }
  );

  server.registerTool(
    "run_pr_relaxation",
    {
      title: "Run Phase-Resolved relaxation (AdaptiveCAD)",
      description:
        "Runs a minimal Phase-Resolved (PR) phase-field relaxation loop and returns energy/coherence metrics.",
      inputSchema: runPrRelaxationInputSchema,
      _meta: {
        "openai/outputTemplate": "ui://widget/adaptivecad.html",
        "openai/toolInvocation/invoking": "Running PR relaxation",
        "openai/toolInvocation/invoked": "Finished PR relaxation",
      },
    },
    async (args) => {
      const size = Number(args?.size ?? 64);
      const steps = Number(args?.steps ?? 200);
      const dt = Number(args?.dt ?? 0.15);
      const diffusion = Number(args?.diffusion ?? 0.35);
      const coupling = Number(args?.coupling ?? 0.25);
      const phase_dim = Number(args?.phase_dim ?? 2);
      const phase_space = String(args?.phase_space ?? "unwrapped");
      const coupling_mode = String(args?.coupling_mode ?? "geom_target");
      const seed = Number(args?.seed ?? 0);

      if (
        !Number.isFinite(size) ||
        !Number.isFinite(steps) ||
        !Number.isFinite(dt) ||
        !Number.isFinite(diffusion) ||
        !Number.isFinite(coupling) ||
        !Number.isFinite(phase_dim)
      ) {
        return replyWithRuns("Invalid parameters.");
      }

      return runPrRelaxation({
        size,
        steps,
        dt,
        diffusion,
        coupling,
        phase_dim,
        phase_space,
        coupling_mode,
        seed,
      });
    }
  );

  server.registerTool(
    "run_pr_and_export_stl",
    {
      title: "Run Phase-Resolved relaxation and export STL (AdaptiveCAD)",
      description:
        "Runs a Phase-Resolved (PR) phase-field relaxation loop, exports the result as a heightmap STL 3D model, and returns metrics + base64-encoded STL data.",
      inputSchema: runPrAndExportStlInputSchema,
      _meta: {
        "openai/outputTemplate": "ui://widget/adaptivecad.html",
        "openai/toolInvocation/invoking": "Running PR relaxation + STL export",
        "openai/toolInvocation/invoked": "Finished PR relaxation + STL export",
      },
    },
    async (args) => {
      const size = Number(args?.size ?? 32);
      const steps = Number(args?.steps ?? 100);
      const dt = Number(args?.dt ?? 0.15);
      const diffusion = Number(args?.diffusion ?? 0.35);
      const coupling = Number(args?.coupling ?? 0.25);
      const phase_dim = Number(args?.phase_dim ?? 2);
      const phase_space = String(args?.phase_space ?? "unwrapped");
      const coupling_mode = String(args?.coupling_mode ?? "geom_target");
      const scale_xy = Number(args?.scale_xy ?? 0.5);
      const scale_z = Number(args?.scale_z ?? 2.0);
      const seed = Number(args?.seed ?? 0);

      if (
        !Number.isFinite(size) ||
        !Number.isFinite(steps) ||
        !Number.isFinite(dt) ||
        !Number.isFinite(diffusion) ||
        !Number.isFinite(coupling) ||
        !Number.isFinite(phase_dim) ||
        !Number.isFinite(scale_xy) ||
        !Number.isFinite(scale_z)
      ) {
        return replyWithRuns("Invalid parameters.");
      }

      return runPrAndExportStl({
        size,
        steps,
        dt,
        diffusion,
        coupling,
        phase_dim,
        phase_space,
        coupling_mode,
        scale_xy,
        scale_z,
        seed,
      });
    }
  );

  server.registerTool(
    "run_pr_and_export_ama",
    {
      title: "Run Phase-Resolved relaxation and export AMA (AdaptiveCAD)",
      description:
        "Runs a Phase-Resolved (PR) phase-field relaxation loop, exports the result as an AdaptiveCAD .ama archive via the OCC kernel, and returns metrics + base64-encoded AMA data.",
      inputSchema: runPrAndExportAmaInputSchema,
      _meta: {
        "openai/outputTemplate": "ui://widget/adaptivecad.html",
        "openai/toolInvocation/invoking": "Running PR relaxation + AMA export",
        "openai/toolInvocation/invoked": "Finished PR relaxation + AMA export",
      },
    },
    async (args) => {
      const size = Number(args?.size ?? 32);
      const steps = Number(args?.steps ?? 100);
      const dt = Number(args?.dt ?? 0.15);
      const diffusion = Number(args?.diffusion ?? 0.35);
      const coupling = Number(args?.coupling ?? 0.25);
      const phase_dim = Number(args?.phase_dim ?? 2);
      const phase_space = String(args?.phase_space ?? "unwrapped");
      const coupling_mode = String(args?.coupling_mode ?? "geom_target");
      const scale_xy = Number(args?.scale_xy ?? 0.5);
      const scale_z = Number(args?.scale_z ?? 2.0);
      const units = String(args?.units ?? "mm");
      const defl = Number(args?.defl ?? 0.05);
      const seed = Number(args?.seed ?? 0);

      if (
        !Number.isFinite(size) ||
        !Number.isFinite(steps) ||
        !Number.isFinite(dt) ||
        !Number.isFinite(diffusion) ||
        !Number.isFinite(coupling) ||
        !Number.isFinite(phase_dim) ||
        !Number.isFinite(scale_xy) ||
        !Number.isFinite(scale_z) ||
        !Number.isFinite(defl)
      ) {
        return replyWithRuns("Invalid parameters.");
      }

      return runPrAndExportAma({
        size,
        steps,
        dt,
        diffusion,
        coupling,
        phase_dim,
        phase_space,
        coupling_mode,
        scale_xy,
        scale_z,
        units,
        defl,
        seed,
      });
    }
  );

  server.registerTool(
    "list_runs",
    {
      title: "List runs",
      description: "Returns recent AdaptiveCAD runs.",
      inputSchema: {},
      _meta: {
        "openai/outputTemplate": "ui://widget/adaptivecad.html",
      },
    },
    async () => replyWithRuns("")
  );

  return server;
}

const port = Number(process.env.PORT ?? 8787);
const MCP_PATH = "/mcp";

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk.toString("utf8");
      if (body.length > 1_000_000) {
        reject(new Error("Body too large"));
      }
    });
    req.on("end", () => {
      if (!body.trim()) return resolve({});
      try {
        resolve(JSON.parse(body));
      } catch (e) {
        reject(e);
      }
    });
  });
}

const httpServer = createServer(async (req, res) => {
  if (!req.url) {
    res.writeHead(400).end("Missing URL");
    return;
  }

  const url = new URL(req.url, `http://${req.headers.host ?? "localhost"}`);

  if (req.method === "OPTIONS" && url.pathname === MCP_PATH) {
    res.writeHead(204, {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
      "Access-Control-Allow-Headers": "content-type, mcp-session-id",
      "Access-Control-Expose-Headers": "Mcp-Session-Id",
    });
    res.end();
    return;
  }

  if (req.method === "GET" && url.pathname === "/") {
    res
      .writeHead(200, { "content-type": "text/plain" })
      .end("AdaptiveCAD MCP server");
    return;
  }

  // Minimal JSON API for the Analytic Viewport (optional; keeps MCP intact)
  if (req.method === "GET" && url.pathname === "/api/health") {
    res
      .writeHead(200, { "content-type": "application/json", "Access-Control-Allow-Origin": "*" })
      .end(JSON.stringify({ ok: true, service: "adaptivecad", mcp: true }));
    return;
  }

  if (req.method === "OPTIONS" && url.pathname.startsWith("/api/")) {
    res.writeHead(204, {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
      "Access-Control-Allow-Headers": "content-type",
    });
    res.end();
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/pr/export_ama") {
    try {
      const body = await readJsonBody(req);
      const parsed = z.object(runPrAndExportAmaInputSchema).parse(body ?? {});

      const argv = [
        bridgePath,
        "run_pr_and_export_ama",
        "--size",
        String(parsed.size),
        "--steps",
        String(parsed.steps),
        "--dt",
        String(parsed.dt),
        "--diffusion",
        String(parsed.diffusion),
        "--coupling",
        String(parsed.coupling),
        "--coupling-mode",
        String(parsed.coupling_mode),
        "--phase-dim",
        String(parsed.phase_dim),
        "--phase-space",
        String(parsed.phase_space),
        "--scale-xy",
        String(parsed.scale_xy),
        "--scale-z",
        String(parsed.scale_z),
        "--units",
        String(parsed.units),
        "--defl",
        String(parsed.defl),
        "--seed",
        String(parsed.seed),
        "--return",
        "path",
      ];

      const env = { ...process.env, MPLBACKEND: "Agg" };
      const command = condaExe || pythonExe;
      const args = condaExe
        ? ["run", "-n", condaEnvName, "python", ...argv]
        : argv;

      const exec = await spawnWithTimeout(
        command,
        args,
        { cwd: adaptiveCadRoot, env, windowsHide: true },
        60_000
      );

      if (exec.code !== 0) {
        const output = [exec.stdout?.trim(), exec.stderr?.trim()].filter(Boolean).join("\n\n");
        res
          .writeHead(500, { "content-type": "application/json", "Access-Control-Allow-Origin": "*" })
          .end(JSON.stringify({ ok: false, error: output || `Python failed (code ${exec.code ?? "?"})` }));
        return;
      }

      const out = parseJsonLoose(exec.stdout);
      if (!out || typeof out !== "object") {
        res
          .writeHead(500, { "content-type": "application/json", "Access-Control-Allow-Origin": "*" })
          .end(JSON.stringify({ ok: false, error: "Invalid JSON from Python bridge" }));
        return;
      }

      res
        .writeHead(200, { "content-type": "application/json", "Access-Control-Allow-Origin": "*" })
        .end(JSON.stringify(out));
    } catch (e) {
      res
        .writeHead(400, { "content-type": "application/json", "Access-Control-Allow-Origin": "*" })
        .end(JSON.stringify({ ok: false, error: String(e?.message ?? e) }));
    }
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/demo/blackholes") {
    try {
      const body = await readJsonBody(req);
      const size = Math.max(8, Math.min(512, Number(body?.size ?? 128)));
      const scale_xy = Number(body?.scale_xy ?? 1.0);
      const scale_z = Number(body?.scale_z ?? 1.0);

      const argv = [
        bridgePath,
        "gen_blackholes_ama",
        "--size",
        String(size),
        "--scale-xy",
        String(scale_xy),
        "--scale-z",
        String(scale_z),
      ];

      const env = { ...process.env, MPLBACKEND: "Agg" };

      const command = condaExe || pythonExe;
      const args = condaExe
        ? ["run", "-n", condaEnvName, "python", ...argv]
        : argv;

      const exec = await spawnWithTimeout(
        command,
        args,
        { cwd: adaptiveCadRoot, env, windowsHide: true },
        60_000
      );

      if (exec.code !== 0) {
        const output = [exec.stdout?.trim(), exec.stderr?.trim()].filter(Boolean).join("\n\n");
        res
          .writeHead(500, { "content-type": "application/json", "Access-Control-Allow-Origin": "*" })
          .end(JSON.stringify({ ok: false, error: output || `Python failed (code ${exec.code ?? "?"})` }));
        return;
      }

      let parsed;
      try {
        parsed = JSON.parse(exec.stdout);
      } catch {
        parsed = null;
      }
      if (!parsed || typeof parsed !== "object") {
        res
          .writeHead(500, { "content-type": "application/json", "Access-Control-Allow-Origin": "*" })
          .end(JSON.stringify({ ok: false, error: "Invalid JSON from generator" }));
        return;
      }

      res
        .writeHead(200, { "content-type": "application/json", "Access-Control-Allow-Origin": "*" })
        .end(JSON.stringify(parsed));
    } catch (e) {
      res
        .writeHead(400, { "content-type": "application/json", "Access-Control-Allow-Origin": "*" })
        .end(JSON.stringify({ ok: false, error: String(e?.message ?? e) }));
    }
    return;
  }

  const MCP_METHODS = new Set(["POST", "GET", "DELETE"]);
  if (url.pathname === MCP_PATH && req.method && MCP_METHODS.has(req.method)) {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Expose-Headers", "Mcp-Session-Id");

    const server = createAdaptiveCadServer();
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined, // stateless mode
      enableJsonResponse: true,
    });

    res.on("close", () => {
      transport.close();
      server.close();
    });

    try {
      await server.connect(transport);
      await transport.handleRequest(req, res);
    } catch (error) {
      console.error("Error handling MCP request:", error);
      if (!res.headersSent) {
        res.writeHead(500).end("Internal server error");
      }
    }
    return;
  }

  res.writeHead(404).end("Not Found");
});

httpServer.listen(port, () => {
  console.log(`AdaptiveCAD MCP server listening on http://localhost:${port}${MCP_PATH}`);
  console.log(`Using Python: ${pythonExe}`);
});

httpServer.on('error', (err) => {
  console.error(`[server error] ${err.message}`);
  process.exit(1);
});
