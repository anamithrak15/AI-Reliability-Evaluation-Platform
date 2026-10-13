import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as authApi from "../api/auth";
import { ApiError } from "../api/client";
import { AuthProvider } from "../auth/AuthContext";
import { AccountPage, ForgotPasswordPage, ResetPasswordPage, VerifyEmailPage } from "./AccountPages";

vi.mock("../api/auth");

const verified = { id: "u1", email: "me@example.com", created_at: "2026-10-12T10:00:00Z", email_verified_at: "2026-10-12T11:00:00Z" };
const unverified = { ...verified, email_verified_at: null };

function inProvider(ui: React.ReactElement) {
  return render(<AuthProvider>{ui}</AuthProvider>);
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(authApi.fetchMe).mockRejectedValue(new ApiError(401, "not_authenticated", "Sign in"));
});

describe("ForgotPasswordPage", () => {
  it("shows the same confirmation whatever the address", async () => {
    vi.mocked(authApi.forgotPassword).mockResolvedValue(undefined);
    inProvider(<ForgotPasswordPage />);
    await userEvent.type(screen.getByLabelText("Email"), " nobody@example.com ");
    await userEvent.click(screen.getByRole("button", { name: "Send reset link" }));
    expect(await screen.findByRole("status")).toHaveTextContent("If an account exists");
    expect(authApi.forgotPassword).toHaveBeenCalledWith("nobody@example.com");
  });

  it("surfaces throttling", async () => {
    vi.mocked(authApi.forgotPassword).mockRejectedValue(new ApiError(429, "rate_limited", "Too many attempts"));
    inProvider(<ForgotPasswordPage />);
    await userEvent.type(screen.getByLabelText("Email"), "a@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Send reset link" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Too many attempts");
  });
});

describe("ResetPasswordPage", () => {
  it("rejects a short password without calling the API", async () => {
    inProvider(<ResetPasswordPage token="t" />);
    await userEvent.type(screen.getByLabelText("New password"), "short");
    await userEvent.click(screen.getByRole("button", { name: "Update password" }));
    expect(authApi.resetPassword).not.toHaveBeenCalled();
  });

  it("sends the token and new password, then points to sign in", async () => {
    vi.mocked(authApi.resetPassword).mockResolvedValue(undefined);
    inProvider(<ResetPasswordPage token="abc" />);
    await userEvent.type(screen.getByLabelText("New password"), "a brand new passphrase");
    await userEvent.click(screen.getByRole("button", { name: "Update password" }));
    expect(await screen.findByText("Password updated")).toBeInTheDocument();
    expect(authApi.resetPassword).toHaveBeenCalledWith("abc", "a brand new passphrase");
  });

  it("shows an expired-link error and offers a new link", async () => {
    vi.mocked(authApi.resetPassword).mockRejectedValue(new ApiError(400, "invalid_token", "This link is invalid or has expired"));
    inProvider(<ResetPasswordPage token="old" />);
    await userEvent.type(screen.getByLabelText("New password"), "a brand new passphrase");
    await userEvent.click(screen.getByRole("button", { name: "Update password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("invalid or has expired");
    expect(screen.getByRole("link", { name: "Request a new one" })).toHaveAttribute("href", "#/forgot-password");
  });

  it("explains a link with no token", () => {
    inProvider(<ResetPasswordPage token="" />);
    expect(screen.getByText("Reset link incomplete")).toBeInTheDocument();
  });
});

describe("VerifyEmailPage", () => {
  it("confirms a good link", async () => {
    vi.mocked(authApi.verifyEmail).mockResolvedValue(verified);
    inProvider(<VerifyEmailPage token="good" />);
    expect(await screen.findByText(/is verified/)).toBeInTheDocument();
    expect(authApi.verifyEmail).toHaveBeenCalledWith("good");
  });

  it("reports a bad link", async () => {
    vi.mocked(authApi.verifyEmail).mockRejectedValue(new ApiError(400, "invalid_token", "This link is invalid or has expired"));
    inProvider(<VerifyEmailPage token="bad" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("invalid or has expired");
  });
});

describe("AccountPage", () => {
  it("lets an unverified user resend the email", async () => {
    vi.mocked(authApi.fetchMe).mockResolvedValue(unverified);
    vi.mocked(authApi.resendVerification).mockResolvedValue(undefined);
    inProvider(<AccountPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Resend verification email" }));
    expect(await screen.findByText("Verification email sent.")).toBeInTheDocument();
  });

  it("does not offer a resend once verified", async () => {
    vi.mocked(authApi.fetchMe).mockResolvedValue(verified);
    inProvider(<AccountPage />);
    expect(await screen.findByText("verified")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Resend verification email" })).toBeNull();
  });

  it("changes the password and clears the fields", async () => {
    vi.mocked(authApi.fetchMe).mockResolvedValue(verified);
    vi.mocked(authApi.changePassword).mockResolvedValue(verified);
    inProvider(<AccountPage />);
    await userEvent.type(await screen.findByLabelText("Current password"), "old password here");
    await userEvent.type(screen.getByLabelText("New password"), "a brand new passphrase");
    await userEvent.click(screen.getByRole("button", { name: "Change password" }));
    expect(await screen.findByText("Password changed.")).toBeInTheDocument();
    expect(authApi.changePassword).toHaveBeenCalledWith("old password here", "a brand new passphrase");
    await waitFor(() => expect(screen.getByLabelText("Current password")).toHaveValue(""));
  });

  it("shows a wrong-current-password error", async () => {
    vi.mocked(authApi.fetchMe).mockResolvedValue(verified);
    vi.mocked(authApi.changePassword).mockRejectedValue(new ApiError(400, "invalid_credentials", "Current password is incorrect"));
    inProvider(<AccountPage />);
    await userEvent.type(await screen.findByLabelText("Current password"), "wrong password!");
    await userEvent.type(screen.getByLabelText("New password"), "a brand new passphrase");
    await userEvent.click(screen.getByRole("button", { name: "Change password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Current password is incorrect");
  });
});
