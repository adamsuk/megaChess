import React, { useEffect, useRef, useState } from "react";

const REPO = "adamsuk/megaChess";
const FILES = ["common.py", "pieces.py", "positions.py", "board.py", "defs/pieces_defs.json", "runner.py"];
const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js";
const GLYPH: Record<string, string> = {
  pawn: "♟", knight: "♞", bishop: "♝", rook: "♜", queen: "♛", king: "♚",
  checkers_man: "●", checkers_king: "◉",
};

type Cell = { piece_type: string; color: string; has_moved: boolean } | "hole" | null;
type Rule = { deltas?: unknown; sliding?: boolean; directional?: boolean; move_only?: boolean; capture_only?: boolean; jump_capture?: boolean };
type GameState = {
  board: { board_size: number; matrix: Cell[][] };
  turn: string;
  mode: string;
  rules: Record<string, { move_rules: Rule[] }>;
  flags: string[];
  result: string | null;
};

type Pyodide = {
  loadPackage: (name: string) => Promise<void>;
  runPythonAsync: (code: string) => Promise<unknown>;
  globals: { set: (name: string, value: unknown) => void };
  FS: { mkdirTree: (path: string) => void; writeFile: (path: string, data: string) => void };
};

let pyodidePromise: Promise<Pyodide> | null = null;

function loadPyodideScript() {
  const existing = (window as unknown as { loadPyodide?: (options: { indexURL: string }) => Promise<Pyodide> }).loadPyodide;
  if (existing) return Promise.resolve(existing);
  return new Promise<(options: { indexURL: string }) => Promise<Pyodide>>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = PYODIDE;
    script.async = true;
    script.onload = () => resolve((window as unknown as { loadPyodide: (options: { indexURL: string }) => Promise<Pyodide> }).loadPyodide);
    script.onerror = () => reject(new Error("Could not load Pyodide"));
    document.body.appendChild(script);
  });
}

function getPyodide() {
  if (!pyodidePromise) {
    pyodidePromise = (async () => {
      const loadPyodide = await loadPyodideScript();
      return loadPyodide({ indexURL: "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/" });
    })();
  }
  return pyodidePromise;
}

async function install(sourceRef: string) {
  const pyodide = await getPyodide();
  const raw = `https://raw.githubusercontent.com/${REPO}/${sourceRef}`;
  pyodide.FS.mkdirTree("/chess/defs");
  for (const file of FILES) {
    const url = file === "runner.py" ? `${raw}/viz/runner.py` : `${raw}/Chess/${file}`;
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Could not import ${url}`);
    pyodide.FS.writeFile(`/chess/${file}`, await response.text());
  }
  return pyodide;
}

async function call(sourceRef: string, code: string) {
  const pyodide = await install(sourceRef);
  const payload = await pyodide.runPythonAsync(code);
  return JSON.parse(String(payload));
}

export default function MegaChess({ sourceRef = "main" }: { sourceRef?: string }) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [full, setFull] = useState(false);
  const [state, setState] = useState<GameState | null>(null);
  const [selected, setSelected] = useState<number[] | null>(null);
  const [moves, setMoves] = useState<number[][]>([]);
  const [status, setStatus] = useState("Loading Chess rules");
  const [error, setError] = useState("");
  const [mode, setMode] = useState("chess");
  const [piece, setPiece] = useState("knight");

  useEffect(() => {
    const onChange = () => setFull(document.fullscreenElement === rootRef.current);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  const toggleFull = () => {
    const node = rootRef.current;
    if (!node) return;
    if (document.fullscreenElement === node) {
      document.exitFullscreen().catch(() => setError("Could not leave full screen"));
      return;
    }
    node.requestFullscreen().catch(() => setError("Full screen was blocked by the browser"));
  };

  const refresh = () => {
    setStatus(`Importing Chess from ${REPO}@${sourceRef}`);
    call(sourceRef, `
import json, sys
sys.path.insert(0, "/chess")
ns = {}
exec(open("/chess/runner.py").read(), ns)
json.dumps(ns["new_game"]("/chess", mode))
`).then((next) => {
      setState(next);
      setSelected(null);
      setMoves([]);
      setStatus("Rules loaded from Chess/");
      setError("");
    }).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Chess failed");
      setStatus("Chess failed");
    });
  };

  useEffect(() => { refresh(); }, [sourceRef]);

  const select = async (x: number, y: number) => {
    if (!state) return;
    const target = moves.find((move) => move[0] === x && move[1] === y);
    if (selected && target) {
      const pyodide = await getPyodide();
      pyodide.globals.set("game_state", state);
      pyodide.globals.set("start", selected);
      pyodide.globals.set("end", target);
      const next = await call(sourceRef, `
import json, sys
sys.path.insert(0, "/chess")
ns = {}
exec(open("/chess/runner.py").read(), ns)
json.dumps(ns["move"](game_state.to_py(), start.to_py(), end.to_py(), "/chess"))
`);
      setState(next);
      setSelected(null);
      setMoves([]);
      return;
    }
    const piece = state.board.matrix[x][y];
    if (!piece || piece === "hole" || piece.color !== state.turn) {
      setSelected(null);
      setMoves([]);
      return;
    }
    const pyodide = await getPyodide();
    pyodide.globals.set("game_state", state);
    pyodide.globals.set("square", [x, y]);
    const legal = await call(sourceRef, `
import json, sys
sys.path.insert(0, "/chess")
ns = {}
exec(open("/chess/runner.py").read(), ns)
json.dumps(ns["legal"](game_state.to_py(), square.to_py(), "/chess"))
`);
    setSelected([x, y]);
    setMoves(legal);
  };

  const changeRule = async (flag: string, value: boolean) => {
    if (!state) return;
    const pyodide = await getPyodide();
    pyodide.globals.set("game_state", state);
    pyodide.globals.set("piece_type", piece);
    pyodide.globals.set("flag", flag);
    pyodide.globals.set("flag_value", value);
    const next = await call(sourceRef, `
import json, sys
sys.path.insert(0, "/chess")
ns = {}
exec(open("/chess/runner.py").read(), ns)
json.dumps(ns["set_rule"](game_state.to_py(), piece_type, 0, flag, flag_value, "/chess"))
`);
    setState(next);
  };

  const clone = async () => {
    if (!state) return;
    const pyodide = await getPyodide();
    pyodide.globals.set("game_state", state);
    pyodide.globals.set("piece_type", piece);
    const next = await call(sourceRef, `
import json, sys
sys.path.insert(0, "/chess")
ns = {}
exec(open("/chess/runner.py").read(), ns)
json.dumps(ns["clone_piece"](game_state.to_py(), piece_type, "/chess"))
`);
    setState(next);
    setPiece(piece.endsWith("_custom") ? piece : `${piece}_custom`);
  };

  const size = state?.board.board_size || 8;
  const rule = state?.rules?.[piece]?.move_rules?.[0];

  return (
    <div ref={rootRef} className={`mx-auto w-full rounded-lg bg-gray-50 p-4 shadow-sm dark:bg-gray-900 ${full ? "max-w-none min-h-screen" : "max-w-3xl"}`}>
      <h2 className="text-lg font-semibold">megaChess</h2>
      <p className="text-sm text-gray-500">{status}. {state ? `${state.turn} to move${state.check ? ", in check" : ""}.` : ""}</p>
      <details className="my-3 rounded-md border border-gray-200 bg-white p-3 text-sm dark:border-gray-700 dark:bg-gray-950">
        <summary className="cursor-pointer font-medium">How to use it</summary>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-gray-600 dark:text-gray-300">
          <li>Click a piece of the side to move. Legal squares come from Chess/board.py legal_moves_safe.</li>
          <li>Click a highlighted square to move. Castling, en passant and promotion to queen use the existing rules.</li>
          <li>PyGame is stubbed. The window is this board; the movement code is not copied.</li>
        </ul>
      </details>
      {error && <p className="mb-3 text-sm text-red-600">{error}</p>}
      <div className="grid w-full max-w-md gap-0.5" style={{ gridTemplateColumns: `repeat(${size}, minmax(0, 1fr))` }}>
        {Array.from({ length: size * size }, (_, index) => {
          const x = index % size;
          const y = Math.floor(index / size);
          const cell = state?.board.matrix[x]?.[y];
          const piece = cell && cell !== "hole" ? cell : null;
          const isMove = moves.some((move) => move[0] === x && move[1] === y);
          const isSelected = selected?.[0] === x && selected?.[1] === y;
          const light = (x + y) % 2 === 0;
          return (
            <button key={`${x}-${y}`} type="button" onClick={() => select(x, y)} className={`flex aspect-square items-center justify-center text-2xl ${light ? "bg-amber-100" : "bg-amber-800"} ${isSelected ? "ring-2 ring-sky-500" : ""} ${isMove ? "ring-2 ring-emerald-400" : ""}`}>
              <span className={piece?.color === "white" ? "text-white drop-shadow" : "text-gray-950"}>{piece ? GLYPH[piece.piece_type] || "?" : ""}</span>
            </button>
          );
        })}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" className="rounded-full bg-gray-900 px-3 py-1 text-sm text-white dark:bg-white dark:text-gray-900" onClick={refresh}>New game</button>
        <button type="button" className={`rounded-full px-3 py-1 text-sm ${mode === "chess" ? "bg-gray-900 text-white" : "bg-gray-200"}`} onClick={() => setMode("chess")}>Chess</button>
        <button type="button" className={`rounded-full px-3 py-1 text-sm ${mode === "checkers" ? "bg-gray-900 text-white" : "bg-gray-200"}`} onClick={() => setMode("checkers")}>Checkers</button>
        <button type="button" className="rounded-full bg-gray-200 px-3 py-1 text-sm dark:bg-gray-800" onClick={toggleFull}>{full ? "Exit full screen" : "Full screen"}</button>
      </div>
      {state?.result && <p className="mt-3 text-sm font-semibold">{state.result}</p>}
      <div className="mt-4 rounded-md border border-gray-200 bg-white p-3 text-sm dark:border-gray-700 dark:bg-gray-950">
        <p className="font-medium">Piece rules from Chess/defs</p>
        <label className="mt-2 block text-xs text-gray-500">Piece
          <select className="mt-1 w-full rounded border border-gray-300 bg-white px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-950" value={piece} onChange={(event) => setPiece(event.target.value)}>
            {Object.keys(state?.rules || { knight: {} }).map((name) => <option key={name}>{name}</option>)}
          </select>
        </label>
        <div className="mt-2 flex flex-wrap gap-3">
          {(state?.flags || ["sliding", "directional", "move_only", "capture_only", "jump_capture"]).map((flag) => (
            <label key={flag} className="flex items-center gap-1 text-xs">
              <input type="checkbox" checked={Boolean(rule?.[flag as keyof Rule])} onChange={(event) => changeRule(flag, event.target.checked)} />
              {flag}
            </label>
          ))}
        </div>
        <button type="button" className="mt-2 text-xs underline" onClick={clone}>Clone as custom piece</button>
        <p className="mt-2 text-xs text-gray-500">Moves use win_conditions.safe_moves. Chess filters check. Checkers uses legal jumps. Toggles edit the loaded defs in memory.</p>
      </div>
      <p className="mt-4 text-sm"><a className="underline" href={`https://github.com/${REPO}/tree/${sourceRef}`}>megaChess {sourceRef}</a></p>
    </div>
  );
}
