import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { initializeTheme, THEME_STORAGE_KEY } from "./theme";

const previewResponse = () => new Response(new Blob(["png"], { type: "image/png" }), {
  status: 200,
  headers: { "X-Configuration-Hash": "theme-test" },
});

describe("theme", () => {
  let systemIsDark = false;
  let listeners: Set<(event: MediaQueryListEvent) => void>;

  const changeSystemTheme = (dark: boolean) => {
    systemIsDark = dark;
    act(() => {
      listeners.forEach((listener) => listener({ matches: dark } as MediaQueryListEvent));
    });
  };

  beforeEach(() => {
    vi.useFakeTimers();
    listeners = new Set();
    systemIsDark = false;
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.style.colorScheme = "";
    vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
      matches: systemIsDark,
      media: query,
      onchange: null,
      addEventListener: (_type: string, listener: (event: MediaQueryListEvent) => void) => listeners.add(listener),
      removeEventListener: (_type: string, listener: (event: MediaQueryListEvent) => void) => listeners.delete(listener),
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => true,
    })));
    vi.stubGlobal("fetch", vi.fn(async () => previewResponse()));
  });

  afterEach(() => {
    cleanup();
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.style.colorScheme = "";
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("initializes from the system and follows live changes before an override", () => {
    systemIsDark = true;
    expect(initializeTheme()).toBe("dark");
    render(<App />);

    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(screen.getByRole("img", { name: "MATCH COW" })).toHaveAttribute("src", "/cow_dark.png");
    expect(screen.getByRole("button", { name: "Switch to light theme" })).toBeInTheDocument();

    changeSystemTheme(false);

    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    expect(screen.getByRole("img", { name: "MATCH COW" })).toHaveAttribute("src", "/cow_light.png");
    expect(screen.getByRole("button", { name: "Switch to dark theme" })).toBeInTheDocument();
  });

  it("persists a manual toggle without disturbing board or preview state", async () => {
    initializeTheme();
    const first = render(<App />);
    fireEvent.change(screen.getByLabelText("Rows"), { target: { value: "9" } });
    await act(async () => { await vi.advanceTimersByTimeAsync(300); });
    vi.mocked(fetch).mockClear();

    fireEvent.click(screen.getByRole("button", { name: "Switch to dark theme" }));

    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(screen.getByLabelText("Rows")).toHaveValue(9);
    await act(async () => { await vi.advanceTimersByTimeAsync(500); });
    expect(fetch).not.toHaveBeenCalled();

    changeSystemTheme(false);
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");

    first.unmount();
    render(<App />);
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(screen.getByRole("img", { name: "MATCH COW" })).toHaveAttribute("src", "/cow_dark.png");
    expect(screen.getByRole("button", { name: "Switch to light theme" })).toBeInTheDocument();
  });
});
