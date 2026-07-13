import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
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
    expect(document.querySelectorAll(".board-pattern")).toHaveLength(3);
    fireEvent.click(screen.getByRole("radio", { name: "Checkerboard" }));
    await act(async () => Promise.resolve());
    expect(screen.getByRole("spinbutton", { name: "Border (mm)" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Dictionary")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Board geometry" }));
    expect(screen.getByRole("button", { name: "Board geometry" })).toHaveAttribute("aria-expanded", "false");
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
    expect(screen.getByRole("button", { name: "Coordinate frame" }).compareDocumentPosition(alert) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByRole("button", { name: "Fit to page" })).toBeInTheDocument();
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
});
