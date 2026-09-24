import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const listIdentityLinksMock = vi.fn();
vi.mock("@/features/identity-links/api/list-identity-links", () => ({
  listIdentityLinks: (...args: unknown[]) => listIdentityLinksMock(...args),
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

const { usePendingIdentityLinks, PENDING_LINKS_PAGE_SIZE } = await import(
  "@/features/identity-links/hooks/use-pending-identity-links"
);

function review(id: number, status: "pending" | "approved" | "rejected" = "pending") {
  return {
    id,
    matchMethod: "fuzzy_name" as const,
    matchConfidence: 0.87,
    status,
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

function page(items: ReturnType<typeof review>[], total: number, offset = 0) {
  return { items, total, limit: PENDING_LINKS_PAGE_SIZE, offset };
}

describe("usePendingIdentityLinks", () => {
  beforeEach(() => {
    listIdentityLinksMock.mockReset();
    approveIdentityLinkMock.mockReset();
    rejectIdentityLinkMock.mockReset();
    reassignIdentityLinkMock.mockReset();
  });

  it("loads the first page of pending reviews", async () => {
    listIdentityLinksMock.mockResolvedValue(page([review(1), review(2)], 2));

    const { result } = renderHook(() => usePendingIdentityLinks());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.reviews).toHaveLength(2);
    expect(result.current.total).toBe(2);
    expect(result.current.page).toBe(1);
    expect(result.current.totalPages).toBe(1);
    expect(result.current.status).toBe("pending");
    expect(result.current.loadError).toBeNull();
    expect(listIdentityLinksMock).toHaveBeenCalledWith("pending", PENDING_LINKS_PAGE_SIZE, 0);
  });

  it("surfaces a load error without crashing", async () => {
    listIdentityLinksMock.mockRejectedValue(new Error("network"));

    const { result } = renderHook(() => usePendingIdentityLinks());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.reviews).toEqual([]);
    expect(result.current.loadError).toBe("Couldn't load pending matches");
  });

  it("computes totalPages from total and the fixed page size", async () => {
    listIdentityLinksMock.mockResolvedValue(
      page(
        Array.from({ length: PENDING_LINKS_PAGE_SIZE }, (_, i) => review(i + 1)),
        PENDING_LINKS_PAGE_SIZE + 5,
      ),
    );

    const { result } = renderHook(() => usePendingIdentityLinks());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.totalPages).toBe(2);
  });

  it("fetches the next page's offset when goToPage is called", async () => {
    listIdentityLinksMock.mockResolvedValueOnce(
      page(
        Array.from({ length: PENDING_LINKS_PAGE_SIZE }, (_, i) => review(i + 1)),
        PENDING_LINKS_PAGE_SIZE + 5,
      ),
    );
    const { result } = renderHook(() => usePendingIdentityLinks());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    listIdentityLinksMock.mockResolvedValueOnce(
      page([review(51)], PENDING_LINKS_PAGE_SIZE + 5, PENDING_LINKS_PAGE_SIZE),
    );
    act(() => {
      result.current.goToPage(2);
    });

    await waitFor(() => expect(result.current.page).toBe(2));
    expect(listIdentityLinksMock).toHaveBeenLastCalledWith(
      "pending",
      PENDING_LINKS_PAGE_SIZE,
      PENDING_LINKS_PAGE_SIZE,
    );
  });

  it("re-fetches the current page once a link is approved", async () => {
    listIdentityLinksMock.mockResolvedValueOnce(page([review(1), review(2)], 2));
    const { result } = renderHook(() => usePendingIdentityLinks());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    approveIdentityLinkMock.mockResolvedValue(undefined);
    listIdentityLinksMock.mockResolvedValueOnce(page([review(2)], 1));

    await act(async () => {
      await result.current.approve(1);
    });

    expect(approveIdentityLinkMock).toHaveBeenCalledWith(1);
    expect(result.current.reviews.map((r) => r.id)).toEqual([2]);
    expect(result.current.total).toBe(1);
  });

  it("re-fetches the current page once a link is rejected", async () => {
    listIdentityLinksMock.mockResolvedValueOnce(page([review(1)], 1));
    const { result } = renderHook(() => usePendingIdentityLinks());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    rejectIdentityLinkMock.mockResolvedValue(undefined);
    listIdentityLinksMock.mockResolvedValueOnce(page([], 0));

    await act(async () => {
      await result.current.reject(1);
    });

    expect(rejectIdentityLinkMock).toHaveBeenCalledWith(1);
    expect(result.current.reviews).toEqual([]);
  });

  it("re-fetches the current page once a link is reassigned to a corrected match", async () => {
    listIdentityLinksMock.mockResolvedValueOnce(page([review(1)], 1));
    const { result } = renderHook(() => usePendingIdentityLinks());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    reassignIdentityLinkMock.mockResolvedValue(undefined);
    listIdentityLinksMock.mockResolvedValueOnce(page([], 0));

    await act(async () => {
      await result.current.reassign(1, 990602);
    });

    expect(reassignIdentityLinkMock).toHaveBeenCalledWith(1, 990602);
    expect(result.current.reviews).toEqual([]);
  });

  it("falls back a page when the current page's last item is removed but more pages remain", async () => {
    // On page 2 of 2, rejecting the sole remaining item leaves page 2
    // empty -- the hook should land back on page 1 instead of showing
    // nothing with page 1 still available.
    listIdentityLinksMock.mockResolvedValueOnce(
      page([review(51)], PENDING_LINKS_PAGE_SIZE + 1, PENDING_LINKS_PAGE_SIZE),
    );
    const { result } = renderHook(() => usePendingIdentityLinks());
    act(() => {
      result.current.goToPage(2);
    });
    await waitFor(() => expect(result.current.page).toBe(2));

    rejectIdentityLinkMock.mockResolvedValue(undefined);
    listIdentityLinksMock.mockResolvedValueOnce(
      page([], PENDING_LINKS_PAGE_SIZE, PENDING_LINKS_PAGE_SIZE),
    );
    listIdentityLinksMock.mockResolvedValueOnce(
      page(
        Array.from({ length: PENDING_LINKS_PAGE_SIZE }, (_, i) => review(i + 1)),
        PENDING_LINKS_PAGE_SIZE,
      ),
    );

    await act(async () => {
      await result.current.reject(51);
    });

    await waitFor(() => expect(result.current.page).toBe(1));
    expect(result.current.reviews).toHaveLength(PENDING_LINKS_PAGE_SIZE);
  });

  it("leaves the list untouched when an action fails", async () => {
    listIdentityLinksMock.mockResolvedValueOnce(page([review(1)], 1));
    const { result } = renderHook(() => usePendingIdentityLinks());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    approveIdentityLinkMock.mockRejectedValue(new Error("conflict"));

    await expect(
      act(async () => {
        await result.current.approve(1);
      }),
    ).rejects.toThrow("conflict");
    expect(result.current.reviews.map((r) => r.id)).toEqual([1]);
    expect(listIdentityLinksMock).toHaveBeenCalledTimes(1);
  });

  it("re-fetches with the new status and resets to page 1 when changeStatus is called", async () => {
    listIdentityLinksMock.mockResolvedValueOnce(
      page([review(51)], PENDING_LINKS_PAGE_SIZE + 1, PENDING_LINKS_PAGE_SIZE),
    );
    const { result } = renderHook(() => usePendingIdentityLinks());
    act(() => {
      result.current.goToPage(2);
    });
    await waitFor(() => expect(result.current.page).toBe(2));

    listIdentityLinksMock.mockResolvedValueOnce(page([review(2, "approved")], 1));
    act(() => {
      result.current.changeStatus("approved");
    });

    await waitFor(() => expect(result.current.status).toBe("approved"));
    expect(result.current.page).toBe(1);
    expect(listIdentityLinksMock).toHaveBeenLastCalledWith("approved", PENDING_LINKS_PAGE_SIZE, 0);
    await waitFor(() =>
      expect(result.current.reviews.map((r) => r.id)).toEqual([2]),
    );
  });
});
