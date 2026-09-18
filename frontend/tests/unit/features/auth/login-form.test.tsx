import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/client";

const pushMock = vi.fn();
const refreshMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, refresh: refreshMock }),
}));

const loginMock = vi.fn();
vi.mock("@/features/auth/api/login", () => ({
  login: (...args: unknown[]) => loginMock(...args),
}));

// Import after the mocks above so the component picks them up.
const { LoginForm } = await import("@/features/auth/components/login-form");

describe("LoginForm", () => {
  beforeEach(() => {
    pushMock.mockClear();
    refreshMock.mockClear();
    loginMock.mockReset();
  });

  it("shows validation errors and never calls the API when the form is empty", async () => {
    const user = userEvent.setup();
    render(<LoginForm />);

    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/email is required/i)).toBeInTheDocument();
    expect(loginMock).not.toHaveBeenCalled();
  });

  it("submits valid credentials and redirects to / on success", async () => {
    loginMock.mockResolvedValueOnce(undefined);
    const user = userEvent.setup();
    render(<LoginForm />);

    await user.type(screen.getByLabelText(/email/i), "admin@football.ai");
    await user.type(screen.getByLabelText(/^password/i), "local-dev-password");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(loginMock).toHaveBeenCalledWith({
        email: "admin@football.ai",
        password: "local-dev-password",
      });
    });
    expect(pushMock).toHaveBeenCalledWith("/");
  });

  it("shows the backend's error message on invalid credentials, without redirecting", async () => {
    loginMock.mockRejectedValueOnce(new ApiError("Invalid email or password", 401));
    const user = userEvent.setup();
    render(<LoginForm />);

    await user.type(screen.getByLabelText(/email/i), "admin@football.ai");
    await user.type(screen.getByLabelText(/^password/i), "wrong-password");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText("Invalid email or password")).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });
});
