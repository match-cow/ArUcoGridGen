import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Check, CircleQuestionMark, ExternalLink, FileDown, Grid2X2, Moon, PanelTop, RectangleHorizontal, RectangleVertical, RotateCcw, Sun } from "lucide-react";
import type { components } from "./api-types";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "./components/ui/accordion";
import { Alert } from "./components/ui/alert";
import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { Card } from "./components/ui/card";
import { Input } from "./components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./components/ui/select";
import { Switch } from "./components/ui/switch";
import { Toast, ToastAction, ToastDescription, ToastProvider, ToastTitle, ToastViewport } from "./components/ui/toast";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "./components/ui/tooltip";
import { useTheme } from "./theme";

type GenerateRequest = components["schemas"]["GenerateRequest"];
type Board = GenerateRequest["board"];
type BoardType = Board["type"];
type PaperSize = GenerateRequest["page"]["paper_size"];
type Orientation = GenerateRequest["page"]["orientation"];
type FitResponse = components["schemas"]["FitResponse"];
type Status = "loading" | "current" | "stale" | "validation-error" | "service-error";
interface ApiError { code: string; path: (string | number)[]; message: string; required_mm?: Record<string, number>; available_mm?: Record<string, number>; }

const dictionaries = ["DICT_4X4_50", "DICT_4X4_100", "DICT_4X4_250", "DICT_4X4_1000", "DICT_5X5_50", "DICT_5X5_100", "DICT_5X5_250", "DICT_5X5_1000", "DICT_6X6_50", "DICT_6X6_100", "DICT_6X6_250", "DICT_6X6_1000", "DICT_7X7_50", "DICT_7X7_100", "DICT_7X7_250", "DICT_7X7_1000"];
const arucoDictionaries = [...dictionaries, "DICT_ARUCO_ORIGINAL", "DICT_APRILTAG_16h5", "DICT_APRILTAG_25h9", "DICT_APRILTAG_36h10", "DICT_APRILTAG_36h11", "DICT_ARUCO_MIP_36h12"];
const boardDefaults: Record<BoardType, Board> = {
  aruco: { type: "aruco", dictionary: "DICT_5X5_100", rows: 7, columns: 5, marker_size_mm: 30, separation_mm: 10, show_ids: false, id_font_size_pt: 8 },
  charuco: { type: "charuco", dictionary: "DICT_5X5_250", squares_x: 5, squares_y: 7, square_size_mm: 30, marker_size_mm: 18 },
  checkerboard: { type: "checkerboard", squares_x: 5, squares_y: 8, square_size_mm: 30, border_mm: 20 },
};
const initial: GenerateRequest = {
  schema_version: "2.0", page: { paper_size: "A4", orientation: "portrait" }, board: boardDefaults.aruco,
  print_compensation: { x_percent: 100, y_percent: 100 },
  annotations: { show_ruler: true, show_parameters: true, show_frame_legend: false },
  coordinate_frame: { enabled: false, pose: { translation_x_m: 0, translation_y_m: 0, translation_z_m: 0, roll_deg: 0, pitch_deg: 0, yaw_deg: 0 } },
};
const paperSizes: Record<PaperSize, [number, number]> = { A4: [210, 297], A3: [297, 420], A2: [420, 594], A1: [594, 841], Letter: [215.9, 279.4], Legal: [215.9, 355.6] };
const layoutKey = (type: BoardType, paper: PaperSize, orientation: Orientation) => `${type}:${paper}:${orientation}`;
const pageLabel = (request: GenerateRequest) => `${request.page.paper_size} ${request.page.orientation}`;
const arucoCardMarkers = [
  { id: 0, x: 6, y: 5, bits: ["10100", "01011", "01100", "10101", "11100"] },
  { id: 1, x: 29, y: 5, bits: ["00001", "11000", "00001", "10111", "00110"] },
  { id: 5, x: 6, y: 28, bits: ["11101", "01000", "00010", "00001", "01101"] },
  { id: 6, x: 29, y: 28, bits: ["01101", "00111", "10101", "11111", "01100"] },
] as const;

function NumberField({ label, value, onChange, min, max, step = 1, unit, description, error }: { label: string; value: number; onChange: (n: number) => void; min?: number; max?: number; step?: number; unit?: string; description?: string; error?: string }) {
  const id = label.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-");
  return <label className="field" htmlFor={id}><span className="field-label">{label}</span><div className="input-unit"><Input id={id} type="number" value={Number.isNaN(value) ? "" : value} min={min} max={max} step={step} onChange={(event) => onChange(event.target.valueAsNumber)} aria-label={unit ? `${label} (${unit})` : undefined} aria-invalid={!!error} aria-describedby={error ? `${id}-error` : description ? `${id}-description` : undefined} />{unit && <span aria-hidden>{unit}</span>}</div>{description && <small id={`${id}-description`}>{description}</small>}{error && <small className="field-error" id={`${id}-error`}>{error}</small>}</label>;
}

function SwitchField({ label, description, checked, onCheckedChange }: { label: string; description?: string; checked: boolean; onCheckedChange: (value: boolean) => void }) {
  const id = label.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-");
  return <div className="switch-row"><div className="switch-copy"><label htmlFor={id}><span>{label}</span></label>{description && <small id={`${id}-description`}>{description}</small>}</div><Switch id={id} aria-describedby={description ? `${id}-description` : undefined} checked={checked} onCheckedChange={onCheckedChange} /></div>;
}

function BoardPattern({ type }: { type: BoardType }) {
  if (type === "aruco") {
    return <svg className="board-pattern" viewBox="0 0 56 56" aria-hidden="true"><rect className="pattern-frame" x=".5" y=".5" width="55" height="55" rx="5" />{arucoCardMarkers.map((marker) => <g key={marker.id} data-marker-id={marker.id} transform={`translate(${marker.x} ${marker.y})`}><rect width="21" height="21" />{marker.bits.flatMap((row, y) => [...row].map((bit, x) => bit === "1" && <rect className="pattern-paper" key={`${x}-${y}`} x={3 + x * 3} y={3 + y * 3} width="3" height="3" />))}</g>)}</svg>;
  }
  const rows = 6, columns = 5, cell = 8, startX = 8, startY = 4;
  return <svg className="board-pattern" viewBox="0 0 56 56" aria-hidden="true"><rect className="pattern-frame" x=".5" y=".5" width="55" height="55" rx="5" /><rect className="pattern-paper" x={startX} y={startY} width={columns * cell} height={rows * cell} />{Array.from({ length: rows * columns }, (_, index) => {
    const row = Math.floor(index / columns), column = index % columns, x = startX + column * cell, y = startY + row * cell;
    if ((row + column) % 2 === 0) return <rect key={index} x={x} y={y} width={cell} height={cell} />;
    if (type === "charuco") return <g key={index}><rect x={x + 1.5} y={y + 1.5} width={5} height={5} /><rect className="pattern-paper" x={x + 2.5} y={y + 2.5} width={1.5} height={1.5} /><rect className="pattern-paper" x={x + 4.5} y={y + 4.5} width={1} height={1} /></g>;
    return null;
  })}</svg>;
}

function friendlyError(error: ApiError, request: GenerateRequest) {
  if (error.code === "page_fit") return `This board is too large for ${pageLabel(request)}.`;
  if (error.code === "annotation_fit") return error.path.includes("show_ids") ? "Marker ID labels need more room between targets." : "The board leaves no safe room for the selected annotations.";
  if (error.code === "auto_fit_impossible") return "Automatic fitting cannot find a safe clean-size grid. Try disabling an annotation or reducing the geometry manually.";
  if (error.code === "dictionary_capacity") return "This dictionary does not contain enough markers for the selected grid.";
  return error.message.replace(/^board:\s*/i, "");
}

function fittedMessage(result: FitResponse) {
  const countChanged = result.changes.some((change) => ["board.rows", "board.columns", "board.squares_x", "board.squares_y"].includes(change.field));
  if (countChanged) {
    const board = result.request.board;
    const grid = board.type === "aruco" ? `${board.columns} × ${board.rows} markers` : `${board.squares_x} × ${board.squares_y} squares`;
    const geometryChanged = result.changes.some((change) => change.field.endsWith("_mm"));
    return `Grid reduced to ${grid} for ${pageLabel(result.request)}${geometryChanged ? " with clean millimetre geometry" : "; board geometry kept unchanged"}.`;
  }
  return `Board dimensions reduced to ${(result.scale_factor * 100).toFixed(1)}% using clean millimetre values for ${pageLabel(result.request)}.`;
}

function targetDimensions(request: GenerateRequest): [number, number] {
  const b = request.board, sx = request.print_compensation.x_percent / 100, sy = request.print_compensation.y_percent / 100;
  if (b.type === "aruco") return [(b.columns * b.marker_size_mm + (b.columns - 1) * b.separation_mm) * sx, (b.rows * b.marker_size_mm + (b.rows - 1) * b.separation_mm) * sy];
  if (b.type === "charuco") return [b.squares_x * b.square_size_mm * sx, b.squares_y * b.square_size_mm * sy];
  return [(b.squares_x * b.square_size_mm + 2 * b.border_mm) * sx, (b.squares_y * b.square_size_mm + 2 * b.border_mm) * sy];
}

export default function App() {
  const { theme, toggleTheme } = useTheme();
  const [config, setConfig] = useState(initial);
  const [frameHelpOpen, setFrameHelpOpen] = useState(false);
  const [status, setStatus] = useState<Status>("loading");
  const [preview, setPreview] = useState<string>();
  const [errors, setErrors] = useState<ApiError[]>([]);
  const [successHash, setSuccessHash] = useState<string>();
  const [retry, setRetry] = useState(0);
  const [fitting, setFitting] = useState(false);
  const [toast, setToast] = useState<{ message: string; previous: GenerateRequest }>();
  const previewSequence = useRef(0), fitSequence = useRef(0), fitController = useRef<AbortController | undefined>(undefined);
  const layouts = useRef<Record<string, GenerateRequest>>({ [layoutKey("aruco", "A4", "portrait")]: initial });
  const boardDrafts = useRef<Record<BoardType, Board>>({ ...boardDefaults });
  const json = useMemo(() => JSON.stringify(config), [config]);

  const commit = (next: GenerateRequest) => {
    setSuccessHash(undefined); setStatus(preview ? "stale" : "loading"); setConfig(next);
    layouts.current[layoutKey(next.board.type, next.page.paper_size, next.page.orientation)] = next;
    boardDrafts.current[next.board.type] = next.board;
  };
  const patchTop = <K extends keyof GenerateRequest>(key: K, value: GenerateRequest[K]) => commit({ ...config, [key]: value });
  const patchBoard = (patch: Partial<Board>) => commit({ ...config, board: { ...config.board, ...patch } as Board });

  const requestFit = async (candidate: GenerateRequest, previous: GenerateRequest, automatic: boolean) => {
    fitController.current?.abort(); const controller = new AbortController(); fitController.current = controller; const sequence = ++fitSequence.current;
    setFitting(true); setErrors([]);
    try {
      const response = await fetch("/api/v2/fit", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(candidate), signal: controller.signal });
      if (sequence !== fitSequence.current) return;
      if (!response.ok) { const body = await response.json(); setErrors(body.errors || []); setStatus("validation-error"); return; }
      const result = await response.json() as FitResponse;
      commit(result.request);
      if (result.adjusted) setToast({ message: fittedMessage(result), previous });
      else if (!automatic) setToast({ message: `The board already fits ${pageLabel(result.request)}.`, previous });
    } catch (error) { if ((error as Error).name !== "AbortError" && sequence === fitSequence.current) setStatus("service-error"); }
    finally { if (sequence === fitSequence.current) setFitting(false); }
  };

  const transition = (page: GenerateRequest["page"], type: BoardType) => {
    const previous = config;
    layouts.current[layoutKey(config.board.type, config.page.paper_size, config.page.orientation)] = config;
    const key = layoutKey(type, page.paper_size, page.orientation);
    const saved = layouts.current[key];
    const board = saved?.board ?? (type === config.board.type ? config.board : boardDrafts.current[type]);
    const candidate = saved ?? { ...config, page, board };
    commit(candidate);
    void requestFit(candidate, previous, true);
  };
  const resetBoard = () => {
    const previous = config, candidate = { ...config, board: boardDefaults[b.type] } as GenerateRequest;
    commit(candidate); void requestFit(candidate, previous, false);
  };
  const boardKeyDown = (event: KeyboardEvent<HTMLButtonElement>, type: BoardType) => {
    const types: BoardType[] = ["aruco", "charuco", "checkerboard"];
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
    event.preventDefault();
    const direction = event.key === "ArrowLeft" || event.key === "ArrowUp" ? -1 : 1;
    const next = types[(types.indexOf(type) + direction + types.length) % types.length];
    transition(config.page, next);
    requestAnimationFrame(() => document.querySelector<HTMLButtonElement>(`[data-board-type="${next}"]`)?.focus());
  };

  useEffect(() => {
    const sequence = ++previewSequence.current, controller = new AbortController();
    setErrors([]); setSuccessHash(undefined); setStatus(preview ? "stale" : "loading");
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch("/api/v2/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: json, signal: controller.signal });
        if (sequence !== previewSequence.current) return;
        if (!response.ok) { if (response.status === 422) { const body = await response.json(); setErrors(body.errors || []); setStatus("validation-error"); } else setStatus("service-error"); return; }
        const blob = await response.blob(); if (sequence !== previewSequence.current) return;
        const url = URL.createObjectURL(blob); setPreview((old) => { if (old) URL.revokeObjectURL(old); return url; });
        setSuccessHash(response.headers.get("X-Configuration-Hash") || "ok"); setStatus("current");
      } catch (error) { if ((error as Error).name !== "AbortError" && sequence === previewSequence.current) setStatus("service-error"); }
    }, 300);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [json, retry]);

  const download = async (kind: "pdf" | "config") => {
    if (!successHash) return;
    const response = await fetch(`/api/v2/exports/${kind}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: json });
    if (!response.ok) { setStatus("service-error"); return; }
    const blob = await response.blob(), url = URL.createObjectURL(blob), anchor = document.createElement("a");
    anchor.href = url; anchor.download = kind === "pdf" ? "calibration-board.pdf" : "calibration-board.json"; anchor.click(); URL.revokeObjectURL(url);
  };
  const undo = () => { if (!toast) return; fitController.current?.abort(); commit(toast.previous); setToast(undefined); };
  const b = config.board;
  const [pageW0, pageH0] = paperSizes[config.page.paper_size], [pageW, pageH] = config.page.orientation === "portrait" ? [pageW0, pageH0] : [pageH0, pageW0];
  const [targetW, targetH] = targetDimensions(config);
  const fitError = errors.some((error) => ["page_fit", "annotation_fit", "auto_fit_impossible"].includes(error.code));
  const fieldError = (...path: string[]) => errors.find((error) => path.every((part, index) => String(error.path[index]) === part))?.message;

  return <TooltipProvider delayDuration={350}><ToastProvider swipeDirection="right">
    <header className="app-header"><div className="brand"><img src={theme === "dark" ? "/cow_dark.png" : "/cow_light.png"} alt="MATCH COW" /><span aria-hidden /><div className="brand-copy"><h1>Calibration Board Studio</h1><p>Print-ready targets with exact geometry</p></div></div><div className="header-actions"><a className="github-link" href="https://github.com/match-cow/ArUcoGridGen" target="_blank" rel="noreferrer" aria-label="View ArUcoGridGen on GitHub"><span>GitHub</span><ExternalLink size={14} aria-hidden /></a><Button className="theme-toggle" variant="outline" size="icon" aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`} onClick={toggleTheme}>{theme === "dark" ? <Sun size={17} aria-hidden /> : <Moon size={17} aria-hidden />}</Button></div></header>
    <main className="app-shell">
      <aside className="inspector" aria-label="Board configuration">
        <div className="inspector-heading"><div><span className="eyebrow">Target type</span><h2>Choose a board</h2></div><Tooltip><TooltipTrigger asChild><Button variant="ghost" size="icon" tabIndex={-1} aria-label="Reset current board" onClick={resetBoard}><RotateCcw size={16} /></Button></TooltipTrigger><TooltipContent>Reset board geometry</TooltipContent></Tooltip></div>
        <div className="board-selectors" role="radiogroup" aria-label="Board type">
          {(["aruco", "charuco", "checkerboard"] as const).map((type) => <button key={type} role="radio" data-board-type={type} tabIndex={b.type === type ? 0 : -1} aria-checked={b.type === type} className={b.type === type ? "board-card selected" : "board-card"} onKeyDown={(event) => boardKeyDown(event, type)} onClick={() => transition(config.page, type)}><BoardPattern type={type} /><span>{type === "aruco" ? "ArUco Grid" : type === "charuco" ? "ChArUco" : "Checkerboard"}</span>{b.type === type && <i className="selected-check"><Check size={12} /></i>}</button>)}
        </div>
        <Accordion type="multiple" defaultValue={["page", "geometry", "print"]} className="section-stack">
          <AccordionItem value="page"><Card><AccordionTrigger><span><PanelTop size={17} />Page</span></AccordionTrigger><AccordionContent><div className="fields two-columns"><label className="field"><span className="field-label">Paper size</span><Select value={config.page.paper_size} onValueChange={(value) => transition({ ...config.page, paper_size: value as PaperSize }, b.type)}><SelectTrigger aria-label="Paper size"><SelectValue /></SelectTrigger><SelectContent>{Object.keys(paperSizes).map((size) => <SelectItem key={size} value={size}>{size}</SelectItem>)}</SelectContent></Select></label><fieldset className="orientation"><legend>Orientation</legend>{(["portrait", "landscape"] as const).map((orientation) => <button key={orientation} type="button" aria-label={orientation[0].toUpperCase() + orientation.slice(1)} aria-pressed={config.page.orientation === orientation} onClick={() => transition({ ...config.page, orientation }, b.type)}>{orientation === "portrait" ? <RectangleVertical size={18} /> : <RectangleHorizontal size={18} />}<span>{orientation}</span></button>)}</fieldset></div></AccordionContent></Card></AccordionItem>
          <AccordionItem value="geometry"><Card><AccordionTrigger><span><Grid2X2 size={17} />Board geometry</span></AccordionTrigger><AccordionContent><div className="fields two-columns">
            {b.type !== "checkerboard" && <label className="field full"><span className="field-label">Dictionary</span><Select value={b.dictionary} onValueChange={(dictionary) => patchBoard({ dictionary })}><SelectTrigger aria-label="Dictionary"><SelectValue /></SelectTrigger><SelectContent>{(b.type === "aruco" ? arucoDictionaries : dictionaries).map((dictionary) => <SelectItem key={dictionary} value={dictionary}>{dictionary}</SelectItem>)}</SelectContent></Select></label>}
            {b.type === "aruco" && <><NumberField label="Rows" value={b.rows} min={1} max={100} onChange={(rows) => patchBoard({ rows })} /><NumberField label="Columns" value={b.columns} min={1} max={100} onChange={(columns) => patchBoard({ columns })} /><NumberField label="Marker size" value={b.marker_size_mm} min={0.1} max={200} step={0.1} unit="mm" onChange={(marker_size_mm) => patchBoard({ marker_size_mm })} /><NumberField label="Separation" value={b.separation_mm} min={0.1} max={200} step={0.1} unit="mm" onChange={(separation_mm) => patchBoard({ separation_mm })} /></>}
            {b.type === "charuco" && <><NumberField label="Squares X" value={b.squares_x} min={2} max={100} onChange={(squares_x) => patchBoard({ squares_x })} /><NumberField label="Squares Y" value={b.squares_y} min={2} max={100} onChange={(squares_y) => patchBoard({ squares_y })} /><NumberField label="Square size" value={b.square_size_mm} min={0.1} max={200} step={0.1} unit="mm" onChange={(square_size_mm) => patchBoard({ square_size_mm })} /><NumberField label="Marker size" value={b.marker_size_mm} min={0.1} max={200} step={0.1} unit="mm" error={fieldError("board", "charuco")} onChange={(marker_size_mm) => patchBoard({ marker_size_mm })} /></>}
            {b.type === "checkerboard" && <><NumberField label="Squares X" value={b.squares_x} min={2} max={100} onChange={(squares_x) => patchBoard({ squares_x })} /><NumberField label="Squares Y" value={b.squares_y} min={2} max={100} onChange={(squares_y) => patchBoard({ squares_y })} /><NumberField label="Square size" value={b.square_size_mm} min={0.1} max={200} step={0.1} unit="mm" onChange={(square_size_mm) => patchBoard({ square_size_mm })} /><NumberField label="Border" value={b.border_mm} min={0} max={100} step={0.1} unit="mm" onChange={(border_mm) => patchBoard({ border_mm })} /></>}
          </div></AccordionContent></Card></AccordionItem>
          <AccordionItem value="print"><Card><AccordionTrigger><span><FileDown size={17} />Print and annotations</span></AccordionTrigger><AccordionContent><div className="fields"><SwitchField label="100 mm scale ruler" description="Physical verification scale" checked={config.annotations.show_ruler} onCheckedChange={(show_ruler) => patchTop("annotations", { ...config.annotations, show_ruler })} /><SwitchField label="Board parameters" checked={config.annotations.show_parameters} onCheckedChange={(show_parameters) => patchTop("annotations", { ...config.annotations, show_parameters })} />{b.type === "aruco" && <><SwitchField label="Marker ID labels" checked={b.show_ids} onCheckedChange={(show_ids) => patchBoard({ show_ids })} />{b.show_ids && <div className="two-columns"><NumberField label="ID font size" value={b.id_font_size_pt} min={6} max={72} unit="pt" onChange={(id_font_size_pt) => patchBoard({ id_font_size_pt })} /></div>}</>}<SwitchField label="Coordinate frame axes" checked={config.annotations.show_frame_legend} onCheckedChange={(show_frame_legend) => patchTop("annotations", { ...config.annotations, show_frame_legend })} /><div className="two-columns"><NumberField label="X compensation" value={config.print_compensation.x_percent} min={0.1} max={200} step={0.1} unit="%" onChange={(x_percent) => patchTop("print_compensation", { ...config.print_compensation, x_percent })} /><NumberField label="Y compensation" value={config.print_compensation.y_percent} min={0.1} max={200} step={0.1} unit="%" onChange={(y_percent) => patchTop("print_compensation", { ...config.print_compensation, y_percent })} /></div></div></AccordionContent></Card></AccordionItem>
          <AccordionItem value="frame"><Card><AccordionTrigger><span><RectangleHorizontal size={17} />Coordinate frame</span></AccordionTrigger><AccordionContent><div className="fields"><div className="feature-help-control"><button type="button" className="help-button" aria-label="What is the coordinate frame feature?" aria-expanded={frameHelpOpen} aria-controls="coordinate-frame-help" onClick={() => setFrameHelpOpen((open) => !open)}><CircleQuestionMark size={16} aria-hidden /></button></div>{frameHelpOpen && <div id="coordinate-frame-help" className="feature-help" role="note"><strong>When is this useful?</strong><p>Use it when the physical board has a known position and orientation in a robot, workcell, or world base frame. The JSON transform maps coordinates measured from the board into that base frame.</p><p>Translation is the board origin’s position in metres. Roll, pitch, and yaw describe its orientation in degrees. The origin is the outer target’s top-left: +X right, +Y down, +Z into the page.</p><p>This does not change the preview or PDF. To print the colored axes, enable <b>Coordinate frame axes</b> under Print and annotations. Leave this off if you only need a printable board.</p></div>}<SwitchField label="Include board-to-base transform" description="Adds a 4×4 matrix and quaternion to the JSON download; no effect on PDF" checked={config.coordinate_frame.enabled} onCheckedChange={(enabled) => patchTop("coordinate_frame", { ...config.coordinate_frame, enabled })} />{config.coordinate_frame.enabled && <fieldset className="pose-fields"><legend>Board pose in base frame</legend><div className="two-columns">{([ ["translation_x_m", "Origin X", "m"], ["translation_y_m", "Origin Y", "m"], ["translation_z_m", "Origin Z", "m"], ["roll_deg", "Roll", "°"], ["pitch_deg", "Pitch", "°"], ["yaw_deg", "Yaw", "°"] ] as const).map(([key, label, unit]) => <NumberField key={key} label={label} unit={unit} value={config.coordinate_frame.pose[key]} step={0.1} onChange={(value) => patchTop("coordinate_frame", { ...config.coordinate_frame, pose: { ...config.coordinate_frame.pose, [key]: value } })} />)}</div></fieldset>}</div></AccordionContent></Card></AccordionItem>
        </Accordion>
      </aside>
      <section className="workspace" aria-live="polite">
        <Card className="preview-toolbar"><div className="preview-meta"><div><strong>Print preview</strong><Badge className={`status ${status}`}>{fitting ? "fitting" : status.replace("-", " ")}</Badge></div><span>{pageW.toFixed(1)} × {pageH.toFixed(1)} mm page <i /> {targetW.toFixed(1)} × {targetH.toFixed(1)} mm target</span></div><div className="actions"><Button disabled={!successHash} onClick={() => void download("pdf")}><FileDown size={16} />Download PDF</Button><Button variant="outline" disabled={!successHash} onClick={() => void download("config")}>Download JSON</Button></div></Card>
        <div className={`paper-wrap ${status !== "current" ? "muted" : ""}`}>{errors.length > 0 && <Alert className="error-summary preview-warning"><div><strong>Check the configuration</strong>{errors.map((error, index) => <p key={index}>{friendlyError(error, config)}</p>)}</div>{fitError && <Button size="sm" variant="outline" disabled={fitting} onClick={() => void requestFit(config, config, false)}>{fitting ? "Fitting…" : "Fit to page"}</Button>}</Alert>}{preview ? <img src={preview} alt="Generated calibration board preview" /> : <div className="skeleton">Generating preview…</div>}{status === "loading" && preview && <div className="overlay">Updating…</div>}</div>
        {status === "service-error" && <p className="preview-message error">The preview service could not be reached. Your settings are preserved. <Button size="sm" variant="outline" onClick={() => setRetry((value) => value + 1)}>Retry</Button></p>}
      </section>
    </main>
    <Toast open={!!toast} onOpenChange={(open) => { if (!open) setToast(undefined); }} duration={7000}><div><ToastTitle>Layout fitted</ToastTitle><ToastDescription>{toast?.message}</ToastDescription></div><ToastAction altText="Undo automatic fit" onClick={undo}>Undo</ToastAction></Toast><ToastViewport />
  </ToastProvider></TooltipProvider>;
}
