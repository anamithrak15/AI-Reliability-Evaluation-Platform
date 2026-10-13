import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as authApi from "./api/auth";
import { ApiError, UNAUTHORIZED_EVENT } from "./api/client";
import * as runsApi from "./api/runs";
import App from "./App";

vi.mock("./api/auth");
vi.mock("./api/runs");
vi.mock("./pages/DatasetsPage", () => ({ default: () => <p>datasets page</p> }));
vi.mock("./pages/RunsPage", () => ({ default: () => <p>runs page</p> }));

const me = { id: "u1", email: "me@example.com", created_at: "2026-10-12T10:00:00Z" };
const signedOut = () => vi.mocked(authApi.fetchMe).mockRejectedValue(new ApiError(401, "not_authenticated", "Sign in"));
const signedIn = () => vi.mocked(authApi.fetchMe).mockResolvedValue(me);

beforeEach(() => {
  vi.mocked(runsApi.listModels).mockResolvedValue([]);
});

describe("sign-in gate", () => {
  it("shows a loading state while it finds out who the user is", () => {
    vi.mocked(authApi.fetchMe).mockReturnValue(new Promise(() => {}));
    render(<App />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });

  it("shows only the sign-in form to visitors, with no data pages or navigation", async () => {
    signedOut();
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByText("datasets page")).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
    expect(runsApi.listModels).not.toHaveBeenCalled();
  });

  it("sends visitors to sign in even when they open a deep link", async () => {
    signedOut();
    window.location.hash = "#/runs";
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByText("runs page")).not.toBeInTheDocument();
  });

  it("offers registration at #/register", async () => {
    signedOut();
    window.location.hash = "#/register";
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Create an account" })).toBeInTheDocument();
  });

  it("tells visitors when the API could not be reached", async () => {
    vi.mocked(authApi.fetchMe).mockRejectedValue(new ApiError(500, "api_unreachable", "Cannot reach the API (status 500)."));
    render(<App />);
    expect(await screen.findByText(/Cannot reach the API/)).toBeInTheDocument();
  });

  it("shows the app, the account and a sign-out button to signed-in users", async () => {
    signedIn();
    render(<App />);
    expect(await screen.findByText("datasets page")).toBeInTheDocument();
    expect(screen.getByText("me@example.com")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });

  it("moves signed-in users away from the sign-in pages", async () => {
    signedIn();
    window.location.hash = "#/login";
    render(<App />);
    await waitFor(() => expect(window.location.hash).toBe("#/datasets"));
    expect(await screen.findByText("datasets page")).toBeInTheDocument();
  });

  it("signs out and returns to the sign-in form", async () => {
    signedIn();
    vi.mocked(authApi.signOut).mockResolvedValue(undefined);
    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));
    expect(authApi.signOut).toHaveBeenCalled();
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByText("me@example.com")).not.toBeInTheDocument();
  });

  it("still signs the user out locally if the sign-out call fails", async () => {
    signedIn();
    vi.mocked(authApi.signOut).mockRejectedValue(new Error("network down"));
    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("returns to sign-in with an explanation when the session expires mid-use", async () => {
    signedIn();
    render(<App />);
    await screen.findByText("datasets page");
    act(() => {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    });
    expect(await screen.findByText(/session has ended/)).toBeInTheDocument();
    expect(screen.queryByText("datasets page")).not.toBeInTheDocument();
  });
});
