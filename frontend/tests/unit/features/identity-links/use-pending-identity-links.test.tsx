import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const listPendingIdentityLinksMock = vi.fn();
vi.mock("@/features/identity-links/api/list-pending-identity-links", () => ({
  listPendingIdentityLinks: (...args: unknown[]) => listPendingIdentityLinksMock(...args),
}));

const approveIdentityLinkMock = vi.fn();
vi.mock("@/features/identity-links/api/approve-identity-link", () => ({
  approveIdentityLink: (...args: unknown[]) => approveIdentityLinkMock(...args),
}));

const rejectIdentityLinkMock = vi.fn();
vi.mock("@/features/identity-links/api/reject-identity-link", () => ({
  rejectIdentityLink: (...args: unknown[]) => rejectIdentityLinkMock(...args),
}));

const reassignIdentityLinkMock = vi.fn();
vi.mock("@/features/identity-links/api/reassign-identity-link", () => ({
  reassignIdentityLink: (...args: unknown[]) => reassignIdentityLinkMock(...args),
}));

const { usePendingIdentityLinks } = await import(
  "@/features/identity-links/hooks/use-pending-identity-links"
);

function review(id: number) {
  return {
    id,
    matchMethod: "fuzzy_name" as const,
    matchConfidence: 0.87,
    status: "pending" as const,
    createdAt: "2026-09-24T17:18:05Z",
    syntheticPlayer: {
      id: 500 + id,
      teamId: 1,
      name: `Player ${id}`,
      nationality: "Testland",
      position: "FW",
      clubTeam: "Test Club",
      marketValueEur: 1000000,
      caps: 10,
      dateOfBirth: "2000-01-01",
      heightCm: 180,
      goals: 5,
    },
    realPlayer: {
      playerId: 990600 + id,
      firstName: "Real",
      lastName: `Player ${id}`,
      dateOfBirth: null,
      countryOfBirth: null,
      countryOfCitizenship: null,
      position: "Forward",
      subPosition: null,
      foot: null,
      heightCm: null,
      currentClubId: null,
      currentNationalTeamId: null,
      internationalCaps: null,
      internationalGoals: null,
      marketValueEur: null,
      highestMarketValueEur: null,
      profileUrl: "https://example.test/player",
    },
  };
}

describe("usePendingIdentityLinks", () => {
  beforeEach(() => {
    listPendingIdentityLinksMock.mockReset();
    approveIdentityLinkMock.mockReset();
    rejectIdentityLinkMock.mockReset();
    reassignIdentityLinkMock.mockReset();
  });

  it("loads pending reviews", async () => {
    listPendingIdentityLinksMock.mockResolvedValue([review(1), review(2)]);

    const { result } = renderHook(() => usePendingIdentityLinks());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.reviews).toHaveLength(2);
    expect(result.current.loadError).toBeNull();
  });

  it("surfaces a load error without crashing", async () => {
    listPendingIdentityLinksMock.mockRejectedValue(new Error("network"));

    const { result } = renderHook(() => usePendingIdentityLinks());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.reviews).toEqual([]);
    expect(result.current.loadError).toBe("Couldn't load pending matches");
  });

  it("removes a link from the list once approved", async () => {
    listPendingIdentityLinksMock.mockResolvedValue([review(1), review(2)]);
    approveIdentityLinkMock.mockResolvedValue(undefined);

    const { result } = renderHook(() => usePendingIdentityLinks());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.approve(1);
    });

    expect(approveIdentityLinkMock).toHaveBeenCalledWith(1);
    expect(result.current.reviews.map((r) => r.id)).toEqual([2]);
  });

  it("removes a link from the list once rejected", async () => {
    listPendingIdentityLinksMock.mockResolvedValue([review(1)]);
    rejectIdentityLinkMock.mockResolvedValue(undefined);

    const { result } = renderHook(() => usePendingIdentityLinks());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.reject(1);
    });

    expect(rejectIdentityLinkMock).toHaveBeenCalledWith(1);
    expect(result.current.reviews).toEqual([]);
  });

  it("removes a link from the list once reassigned to a corrected match", async () => {
    listPendingIdentityLinksMock.mockResolvedValue([review(1)]);
    reassignIdentityLinkMock.mockResolvedValue(undefined);

    const { result } = renderHook(() => usePendingIdentityLinks());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.reassign(1, 990602);
    });

    expect(reassignIdentityLinkMock).toHaveBeenCalledWith(1, 990602);
    expect(result.current.reviews).toEqual([]);
  });

  it("leaves the list untouched when an action fails", async () => {
    listPendingIdentityLinksMock.mockResolvedValue([review(1)]);
    approveIdentityLinkMock.mockRejectedValue(new Error("conflict"));

    const { result } = renderHook(() => usePendingIdentityLinks());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await expect(
      act(async () => {
        await result.current.approve(1);
      }),
    ).rejects.toThrow("conflict");
    expect(result.current.reviews.map((r) => r.id)).toEqual([1]);
  });
});
