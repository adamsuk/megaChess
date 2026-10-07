import React, { useEffect, useRef, useState } from "react";

const REPO = "adamsuk/megaChess";
const FILES = ["common.py", "pieces.py", "positions.py", "board.py", "win_conditions.py", "svg_renderer.py", "game.py", "defs/pieces_defs.json", "runner.py"];
const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js";
const GLYPH: Record<string, string> = {
  pawn: "♟", knight: "♞", bishop: "♝", rook: "♜", queen: "♛", king: "♚",
  checkers_man: "●", checkers_king: "◉",
};
const FLAGS = ["sliding", "directional", "move_only", "capture_only", "jump_capture"];

type Cell = { piece_type: string; color: string; has_moved: boolean } | "hole" | null;
type Rule = Record<string, unknown>;
type Board = { board_size: number; matrix: Cell[][] };
type Rules = Record<string, { move_rules: Rule[] }>;
type GameState = { board: Board; turn: string; mode: string; rules: Rules; result: string | null };
type Screen = "menu" | "pieces" | "layout" | "play";
type Pyodide = {
  runPythonAsync: (code: string) => Promise<unknown>;
  globals: { set: (name: string, value: unknown) => void };
  FS: { mkdirTree: (path: string) => void; writeFile: (path: string, data: string) => void };
};

let pyodidePromise: Promise<Pyodide> | null = null;

function loadPyodideScript() {
  const existing = (window as unknown as { loadPyodide?: (opts: { indexURL: string }) => Promise<Pyodide> }).loadPyodide;
  if (existing) return Promise.resolve(existing);
  return new Promise<(opts: { indexURL: string }) => Promise<Pyodide>>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = PYODIDE;
    script.async = true;
    script.onload = () => resolve((window as unknown as { loadPyodide: (opts: { indexURL: string }) => Promise<Pyodide> }).loadPyodide);
    script.onerror = () => reject(new Error("Could not load Pyodide"));
    document.body.appendChild(script);
  });
}

function getPyodide() {
  if (!pyodidePromise) {
    pyodidePromise = loadPyodideScript().then((load) => load({ indexURL: "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/" }));
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
  await install(sourceRef);
  const payload = await (await getPyodide()).runPythonAsync(code);
  return JSON.parse(String(payload));
}

export default function MegaChess({ sourceRef = "main" }: { sourceRef?: string }) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [screen, setScreen] = useState<Screen>("menu");
  const [rules, setRules] = useState<Rules | null>(null);
  const [layout, setLayout] = useState<Board | null>(null);
  const [piece, setPiece] = useState("knight");
  const [paint, setPaint] = useState("pawn");
  const [state, setState] = useState<GameState | null>(null);
  const [selected, setSelected] = useState<number[] | null>(null);
  const [moves, setMoves] = useState<number[][]>([]);
  const [error, setError] = useState("");
  const [full, setFull] = useState(false);

  useEffect(() => {
    const onChange = () => setFull(document.fullscreenElement === rootRef.current);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  const run = async (code: string) => {
    setError("");
    return call(sourceRef, code);
  };

  const openPieces = async () => {
    setScreen("pieces");
    if (rules) return;
    const next = await run(`
import json, sys
sys.path.insert(0, "/chess")
ns = {}
exec(open("/chess/runner.py").read(), ns)
json.dumps(ns["new_game"]("/chess")["rules"])
`);
    setRules(next);
  };

  const openLayout = async (name = "standard") => {
    setScreen("layout");
    const next = await run(`
import json, sys
sys.path.insert(0, "/chess")
ns = {}
exec(open("/chess/runner.py").read(), ns)
json.dumps(ns["presets"]("/chess")["${name}"])
`);
    setLayout(next);
  };

  const play = async () => {
    setScreen("play");
    const pyodide = await getPyodide();
    pyodide.globals.set("saved_rules", rules ? JSON.stringify(rules) : "");
    pyodide.globals.set("saved_layout", layout ? JSON.stringify(layout) : "");
    const next = await run(`
import json, sys
sys.path.insert(0, "/chess")
ns = {}
exec(open("/chess/runner.py").read(), ns)
rules = json.loads(saved_rules) if saved_rules else None
layout = json.loads(saved_layout) if saved_layout else None
json.dumps(ns["start"]("/chess", "chess", rules, layout))
`);
    setState(next);
    setSelected(null);
    setMoves([]);
  };

  const select = async (x: number, y: number) => {
    if (!state) return;
    const target = moves.find((move) => move[0] === x && move[1] === y);
    const pyodide = await getPyodide();
    if (selected && target) {
      pyodide.globals.set("game_state", state);
      pyodide.globals.set("start", selected);
      pyodide.globals.set("end", target);
      const next = await run(`
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
    const cell = state.board.matrix[x][y];
    if (!cell || cell === "hole" || cell.color !== state.turn) {
      setSelected(null);
      setMoves([]);
      return;
    }
    pyodide.globals.set("game_state", state);
    pyodide.globals.set("square", [x, y]);
    const legal = await run(`
import json, sys
sys.path.insert(0, "/chess")
ns = {}
exec(open("/chess/runner.py").read(), ns)
json.dumps(ns["legal"](game_state.to_py(), square.to_py(), "/chess"))
`);
    setSelected([x, y]);
    setMoves(legal);
  };

  const paintSquare = (x: number, y: number) => {
    if (!layout) return;
    const matrix = layout.matrix.map((col) => col.slice());
    const current = matrix[x][y];
    if (current === "hole") matrix[x][y] = null;
    else if (!current) matrix[x][y] = { piece_type: paint, color: "white", has_moved: false };
    else if (current.color === "white") matrix[x][y] = { ...current, color: "black" };
    else matrix[x][y] = "hole";
    setLayout({ ...layout, matrix });
  };

  const rule = rules?.[piece]?.move_rules?.[0];
  const size = screen === "layout" ? layout?.board_size || 8 : state?.board.board_size || 8;

  return (
    <div ref={rootRef} className={`mx-auto w-full rounded-lg bg-gray-50 p-4 dark:bg-gray-900 ${full ? "max-w-none min-h-screen" : "max-w-3xl"}`}>
      {screen === "menu" && (
        <div className="mx-auto max-w-sm space-y-3 py-8 text-center">
          <h2 className="text-2xl font-semibold">megaChess</h2>
          <p className="text-sm text-gray-500">Loaded from Chess/. Edit pieces or the board, then play.</p>
          <button type="button" className="block w-full rounded-md bg-blue-800 px-4 py-3 text-white" onClick={play}>Play</button>
          <button type="button" className="block w-full rounded-md bg-green-800 px-4 py-3 text-white" onClick={openPieces}>Edit pieces</button>
          <button type="button" className="block w-full rounded-md bg-purple-900 px-4 py-3 text-white" onClick={() => openLayout("standard")}>Edit layout</button>
        </div>
      )}
      {screen !== "menu" && <button type="button" className="mb-3 text-sm underline" onClick={() => setScreen("menu")}>Back to menu</button>}
      {error && <p className="mb-3 text-sm text-red-600">{error}</p>}
      {screen === "pieces" && rules && (
        <div className="space-y-3 text-sm">
          <h2 className="text-lg font-semibold">Edit pieces</h2>
          <select className="w-full rounded border px-2 py-1" value={piece} onChange={(event) => setPiece(event.target.value)}>
            {Object.keys(rules).map((name) => <option key={name}>{name}</option>)}
          </select>
          {FLAGS.map((flag) => (
            <label key={flag} className="flex items-center gap-2">
              <input type="checkbox" checked={Boolean(rule?.[flag])} onChange={(event) => {
                const next = structuredClone(rules);
                next[piece].move_rules[0][flag] = event.target.checked;
                setRules(next);
              }} />
              {flag}
            </label>
          ))}
          <button type="button" className="rounded-md bg-gray-900 px-3 py-2 text-white" onClick={play}>Play with these pieces</button>
        </div>
      )}
      {screen === "layout" && layout && (
        <div>
          <h2 className="mb-2 text-lg font-semibold">Edit layout</h2>
          <div className="mb-3 flex flex-wrap gap-2 text-sm">
            <button type="button" className="rounded-full bg-gray-200 px-3 py-1" onClick={() => openLayout("standard")}>Standard</button>
            <button type="button" className="rounded-full bg-gray-200 px-3 py-1" onClick={() => openLayout("diamond")}>Diamond</button>
            <button type="button" className="rounded-full bg-gray-200 px-3 py-1" onClick={() => openLayout("hexagon")}>Hexagon</button>
            <select value={paint} onChange={(event) => setPaint(event.target.value)}>
              {Object.keys(rules || GLYPH).map((name) => <option key={name}>{name}</option>)}
            </select>
          </div>
          <BoardView size={size} matrix={layout.matrix} onSquare={paintSquare} />
          <button type="button" className="mt-3 rounded-md bg-gray-900 px-3 py-2 text-sm text-white" onClick={play}>Play this layout</button>
        </div>
      )}
      {screen === "play" && state && (
        <div>
          <p className="mb-2 text-sm text-gray-500">{state.turn} to move{state.result ? `. ${state.result}` : ""}</p>
          <BoardView size={size} matrix={state.board.matrix} moves={moves} selected={selected} onSquare={select} />
          <button type="button" className="mt-3 text-sm underline" onClick={() => rootRef.current?.requestFullscreen()}>{full ? "Exit full screen" : "Full screen"}</button>
        </div>
      )}
      <p className="mt-4 text-sm"><a className="underline" href={`https://github.com/${REPO}/tree/${sourceRef}`}>megaChess {sourceRef}</a></p>
    </div>
  );
}

function BoardView({ size, matrix, moves = [], selected, onSquare }: { size: number; matrix: Cell[][]; moves?: number[][]; selected?: number[] | null; onSquare: (x: number, y: number) => void }) {
  return (
    <div className="grid w-full max-w-md gap-0.5" style={{ gridTemplateColumns: `repeat(${size}, minmax(0, 1fr))` }}>
      {Array.from({ length: size * size }, (_, index) => {
        const x = index % size;
        const y = Math.floor(index / size);
        const cell = matrix[x]?.[y];
        const piece = cell && cell !== "hole" ? cell : null;
        const isMove = moves.some((move) => move[0] === x && move[1] === y);
        const isSelected = selected?.[0] === x && selected?.[1] === y;
        const light = (x + y) % 2 === 0;
        return (
          <button key={`${x}-${y}`} type="button" onClick={() => onSquare(x, y)} className={`flex aspect-square items-center justify-center text-2xl ${cell === "hole" ? "bg-gray-700" : light ? "bg-amber-100" : "bg-amber-800"} ${isSelected ? "ring-2 ring-sky-500" : ""} ${isMove ? "ring-2 ring-emerald-400" : ""}`}>
            <span className={piece?.color === "white" ? "text-white drop-shadow" : "text-gray-950"}>{piece ? GLYPH[piece.piece_type] || "?" : ""}</span>
          </button>
        );
      })}
    </div>
  );
}
