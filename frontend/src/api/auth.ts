import { request } from "./client";

export interface User {
  id: string;
  email: string;
  created_at: string;
}

export const fetchMe = () => request<User>("/api/v1/auth/me");

export const registerAccount = (email: string, password: string) =>
  request<User>("/api/v1/auth/register", { method: "POST", body: { email, password } });

export const signIn = (email: string, password: string) =>
  request<User>("/api/v1/auth/login", { method: "POST", body: { email, password } });

export const signOut = () => request<void>("/api/v1/auth/logout", { method: "POST" });
