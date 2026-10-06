import React from "react";
import { createRoot } from "react-dom/client";
import MegaChess from "../src/MegaChess";

const sourceRef = (window as unknown as { MEGACHESS_REF?: string }).MEGACHESS_REF || "main";
const root = document.getElementById("root");
if (!root) throw new Error("missing root");
createRoot(root).render(<main className="mx-auto max-w-4xl p-6"><MegaChess sourceRef={sourceRef} /></main>);
