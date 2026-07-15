import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import type { components } from "./api-types";
type GenerateRequest = components["schemas"]["GenerateRequest"];

const png = () => new Response(new Blob(["png"], { type: "image/png" }), { status: 200, headers: { "X-Configuration-Hash": "abc" } });
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
const fitResult = (request: GenerateRequest, adjusted = false) => ({ request, adjusted, scale_factor: 1, changes: adjusted ? [{ field: "board.rows", before: 7, after: 4 }] : [] });

describe("workspace", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v2/fit")) { const request = JSON.parse(String(init?.body)) as GenerateRequest; return json(fitResult(request)); }
      return png();
    }));
  });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

  it("uses visual board radios, board-specific controls, and collapsible cards", async () => {
    render(<App />);
    expect(screen.getByRole("link", { name: "View ArUcoGridGen on GitHub" })).toHaveAttribute("href", "https://github.com/match-cow/ArUcoGridGen");
    expect(screen.queryByText(/v2 workspace/i)).not.toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "ArUco Grid" })).toBeChecked();
    const geometryCard = screen.getByRole("button", { name: "Board geometry" }).closest<HTMLElement>(".card")!;
    const printCard = screen.getByRole("button", { name: "Print and annotations" }).closest<HTMLElement>(".card")!;
    expect(within(geometryCard).queryByRole("switch", { name: "Marker ID labels" })).not.toBeInTheDocument();
    expect(within(printCard).getByRole("switch", { name: "Marker ID labels" })).not.toBeChecked();
    const frameAxes = within(printCard).getByRole("switch", { name: "Coordinate frame axes" });
    expect(frameAxes).not.toBeChecked();
    expect(frameAxes).not.toHaveAccessibleDescription();
    const frameTrigger = screen.getByRole("button", { name: "Coordinate frame" });
    expect(frameTrigger).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(frameTrigger);
    expect(screen.queryByText("Optional JSON metadata for a known board mounting")).not.toBeInTheDocument();
    const frameHelp = screen.getByRole("button", { name: "What is the coordinate frame feature?" });
    expect(frameHelp).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("When is this useful?")).not.toBeInTheDocument();
    fireEvent.click(frameHelp);
    expect(frameHelp).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("When is this useful?")).toBeInTheDocument();
    expect(screen.getByText(/does not change the preview or PDF/i)).toBeInTheDocument();
    const transformSwitch = screen.getByRole("switch", { name: "Include board-to-base transform" });
    expect(transformSwitch).toHaveAccessibleDescription("Adds a 4×4 matrix and quaternion to the JSON download; no effect on PDF");
    fireEvent.click(transformSwitch);
    expect(screen.getByRole("group", { name: "Board pose in base frame" })).toBeInTheDocument();
    expect(screen.getByRole("spinbutton", { name: "Origin X (m)" })).toHaveValue(0);
    expect(screen.queryByRole("switch", { name: "Frame legend" })).not.toBeInTheDocument();
    expect(screen.queryByRole("spinbutton", { name: "ID font size (pt)" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("switch", { name: "Marker ID labels" }));
    expect(screen.getByRole("switch", { name: "Marker ID labels" })).toBeChecked();
    expect(screen.getByRole("spinbutton", { name: "ID font size (pt)" })).toBeInTheDocument();
    expect(document.querySelectorAll(".board-pattern")).toHaveLength(3);
    fireEvent.click(screen.getByRole("radio", { name: "Checkerboard" }));
    await act(async () => Promise.resolve());
    expect(screen.getByRole("spinbutton", { name: "Border (mm)" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Dictionary")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Board geometry" }));
    expect(screen.getByRole("button", { name: "Board geometry" })).toHaveAttribute("aria-expanded", "false");
  });

  it("renders detector-valid DICT_5X5_100 modules in the ArUco menu card", () => {
    render(<App />);
    const expected = new Map([
      ["0", ["10100", "01011", "01100", "10101", "11100"]],
      ["1", ["00001", "11000", "00001", "10111", "00110"]],
      ["5", ["11101", "01000", "00010", "00001", "01101"]],
      ["6", ["01101", "00111", "10101", "11111", "01100"]],
    ]);

    document.querySelectorAll<SVGGElement>("[data-marker-id]").forEach((marker) => {
      const modules = Array.from({ length: 5 }, () => Array(5).fill("0"));
      marker.querySelectorAll<SVGRectElement>(".pattern-paper").forEach((cell) => {
        const x = (Number(cell.getAttribute("x")) - 3) / 3;
        const y = (Number(cell.getAttribute("y")) - 3) / 3;
        modules[y][x] = "1";
      });
      expect(modules.map((row) => row.join(""))).toEqual(expected.get(marker.dataset.markerId!));
    });
    expect(document.querySelectorAll("[data-marker-id]")).toHaveLength(expected.size);
  });

  it("automatically fits a transition and Undo restores the complete context", async () => {
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      if (String(input).endsWith("/api/v2/fit")) {
        const request = JSON.parse(String(init?.body)) as GenerateRequest;
        if (request.board.type === "aruco") request.board = { ...request.board, rows: 4 };
        return json(fitResult(request, true));
      }
      return png();
    });
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Landscape" }));
    await act(async () => Promise.resolve());
    expect(screen.getByRole("spinbutton", { name: "Rows" })).toHaveValue(4);
    expect(screen.getByText(/Grid reduced to 5 × 4 markers for A4 landscape; board geometry kept unchanged/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(screen.getByRole("button", { name: "Portrait" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("spinbutton", { name: "Marker size (mm)" })).toHaveValue(30);
  });

  it("restores drafts independently for each page orientation", async () => {
    render(<App />);
    fireEvent.change(screen.getByLabelText("Rows"), { target: { value: "9" } });
    fireEvent.click(screen.getByRole("button", { name: "Landscape" }));
    await act(async () => Promise.resolve());
    fireEvent.change(screen.getByLabelText("Rows"), { target: { value: "6" } });
    fireEvent.click(screen.getByRole("button", { name: "Portrait" }));
    await act(async () => Promise.resolve());
    expect(screen.getByLabelText("Rows")).toHaveValue(9);
  });

  it("shows friendly fit errors and offers manual Fit to page", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(json({ errors: [{ code: "page_fit", path: ["board"], message: "board: does not fit" }] }, 422));
    render(<App />);
    await act(async () => { await vi.advanceTimersByTimeAsync(300); });
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("This board is too large for A4 portrait.");
    expect(alert.closest(".paper-wrap")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Fit to page" })).toBeInTheDocument();
    expect(screen.queryByText("The last valid preview is shown. Adjust the geometry or use Fit to page.")).not.toBeInTheDocument();
  });

  it("aborts superseded fit requests", async () => {
    const signals: AbortSignal[] = [];
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      if (String(input).endsWith("/api/v2/fit")) {
        signals.push(init!.signal as AbortSignal);
        const request = JSON.parse(String(init?.body)) as GenerateRequest;
        return json(fitResult(request));
      }
      return png();
    });
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Landscape" }));
    fireEvent.click(screen.getByRole("radio", { name: "ChArUco" }));
    await act(async () => Promise.resolve());
    expect(signals).toHaveLength(2);
    expect(signals[0].aborted).toBe(true);
  });

  it("debounces preview and only enables exports after success", async () => {
    render(<App />);
    expect(screen.getByRole("button", { name: "Download PDF" })).toBeDisabled();
    await act(async () => { await vi.advanceTimersByTimeAsync(300); });
    expect(screen.getByRole("button", { name: "Download PDF" })).toBeEnabled();
    fireEvent.change(screen.getByLabelText("Rows"), { target: { value: "8" } });
    expect(screen.getByRole("button", { name: "Download PDF" })).toBeDisabled();
  });

  it("emits the compatible frame field and refreshes preview for the axes toggle", async () => {
    render(<App />);
    await act(async () => { await vi.advanceTimersByTimeAsync(300); });
    vi.mocked(fetch).mockClear();

    fireEvent.click(screen.getByRole("switch", { name: "Coordinate frame axes" }));
    expect(screen.getByRole("switch", { name: "Coordinate frame axes" })).toBeChecked();
    expect(screen.getByRole("button", { name: "Download PDF" })).toBeDisabled();
    await act(async () => { await vi.advanceTimersByTimeAsync(300); });

    const previewCall = vi.mocked(fetch).mock.calls.find(([input]) =>
      String(input).endsWith("/api/v2/preview")
    );
    expect(previewCall).toBeDefined();
    const emitted = JSON.parse(String(previewCall?.[1]?.body)) as GenerateRequest;
    expect(emitted.annotations.show_frame_legend).toBe(true);
    expect(screen.getByRole("button", { name: "Download PDF" })).toBeEnabled();
  });
});
