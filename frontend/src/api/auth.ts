import { request } from "./client";

export interface User {
  id: string;
  email: string;
  created_at: string;
  // null means the address is not verified yet; absent only in older responses.
  email_verified_at?: string | null;
}

export const fetchMe = () => request<User>("/api/v1/auth/me");

export const registerAccount = (email: string, password: string) =>
  request<User>("/api/v1/auth/register", { method: "POST", body: { email, password } });

export const signIn = (email: string, password: string) =>
  request<User>("/api/v1/auth/login", { method: "POST", body: { email, password } });

export const signOut = () => request<void>("/api/v1/auth/logout", { method: "POST" });

export const verifyEmail = (token: string) =>
  request<User>("/api/v1/auth/verify-email", { method: "POST", body: { token } });

export const resendVerification = () => request<void>("/api/v1/auth/resend-verification", { method: "POST" });

export const forgotPassword = (email: string) =>
  request<void>("/api/v1/auth/forgot-password", { method: "POST", body: { email } });

export const resetPassword = (token: string, password: string) =>
  request<void>("/api/v1/auth/reset-password", { method: "POST", body: { token, password } });

export const changePassword = (current_password: string, new_password: string) =>
  request<User>("/api/v1/auth/change-password", { method: "POST", body: { current_password, new_password } });
