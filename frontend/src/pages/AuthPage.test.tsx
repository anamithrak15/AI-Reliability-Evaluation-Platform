import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as authApi from "../api/auth";
import { ApiError } from "../api/client";
import { AuthProvider } from "../auth/AuthContext";
import AuthPage from "./AuthPage";

vi.mock("../api/auth");

const user = { id: "u1", email: "me@example.com", created_at: "2026-10-12T10:00:00Z" };

function renderPage(mode: "login" | "register", notice?: string) {
  return render(
    <AuthProvider>
      <AuthPage mode={mode} notice={notice} />
    </AuthProvider>,
  );
}

async function fill(email: string, password: string) {
  await userEvent.type(screen.getByLabelText("Email"), email);
  await userEvent.type(screen.getByLabelText("Password"), password);
}

beforeEach(() => {
  vi.mocked(authApi.fetchMe).mockRejectedValue(new ApiError(401, "not_authenticated", "Sign in"));
});

describe("AuthPage sign in", () => {
  it("signs in with a trimmed email and goes to the datasets page", async () => {
    vi.mocked(authApi.signIn).mockResolvedValue(user);
    renderPage("login");
    await fill("  me@example.com ", "a long enough password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(authApi.signIn).toHaveBeenCalledWith("me@example.com", "a long enough password"));
    await waitFor(() => expect(window.location.hash).toBe("#/datasets"));
  });

  it("shows the server's message and re-enables the form on failure", async () => {
    vi.mocked(authApi.signIn).mockRejectedValue(
      new ApiError(401, "invalid_credentials", "Incorrect email or password"),
    );
    renderPage("login");
    await fill("me@example.com", "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password");
    expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
    expect(window.location.hash).not.toBe("#/datasets");
  });

  it("tells the user when they are being throttled", async () => {
    vi.mocked(authApi.signIn).mockRejectedValue(new ApiError(429, "rate_limited", "Too many attempts; wait a minute and try again"));
    renderPage("login");
    await fill("me@example.com", "whatever");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Too many attempts");
  });

  it("disables the button while the request is in flight", async () => {
    vi.mocked(authApi.signIn).mockReturnValue(new Promise(() => {}));
    renderPage("login");
    await fill("me@example.com", "whatever");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(screen.getByRole("button", { name: "Please wait..." })).toBeDisabled();
  });

  it("uses the right autocomplete hints and links to registration", () => {
    renderPage("login");
    expect(screen.getByLabelText("Password")).toHaveAttribute("autocomplete", "current-password");
    expect(screen.getByLabelText("Email")).toHaveAttribute("autocomplete", "email");
    expect(screen.getByRole("link", { name: "Create an account" })).toHaveAttribute("href", "#/register");
  });

  it("shows why the user was sent here", () => {
    renderPage("login", "Your session has ended. Please sign in again.");
    expect(screen.getByText(/session has ended/)).toBeInTheDocument();
  });
});

describe("AuthPage register", () => {
  it("blocks a short password before calling the server", async () => {
    renderPage("register");
    await fill("me@example.com", "short");
    // jsdom does not enforce minLength on submit, so this checks our own validation.
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("at least 10 characters");
    expect(authApi.registerAccount).not.toHaveBeenCalled();
  });

  it("creates the account and signs in", async () => {
    vi.mocked(authApi.registerAccount).mockResolvedValue(user);
    renderPage("register");
    await fill("me@example.com", "a long enough password");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() =>
      expect(authApi.registerAccount).toHaveBeenCalledWith("me@example.com", "a long enough password"),
    );
    await waitFor(() => expect(window.location.hash).toBe("#/datasets"));
  });

  it("reports an email that is already registered", async () => {
    vi.mocked(authApi.registerAccount).mockRejectedValue(
      new ApiError(409, "email_taken", "An account with this email already exists"),
    );
    renderPage("register");
    await fill("me@example.com", "a long enough password");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("already exists");
  });

  it("suggests a password manager friendly new password field", () => {
    renderPage("register");
    expect(screen.getByLabelText("Password")).toHaveAttribute("autocomplete", "new-password");
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "#/login");
  });
});
