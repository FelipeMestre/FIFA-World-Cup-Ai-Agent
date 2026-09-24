"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const ADMIN_NAV_ITEMS = [
  { href: "/identity-links", label: "Identity links" },
  { href: "/sync-jobs", label: "Sync jobs" },
];

/** Top-of-page navigation between the `(admin)` route group's pages.
 * Navigation, not client-side filter state, so each tab is a real link
 * (`usePathname` only decides which one renders active).
 */
export function AdminNavTabs() {
  const pathname = usePathname();
  const activeHref =
    ADMIN_NAV_ITEMS.find((item) => pathname.startsWith(item.href))?.href ??
    ADMIN_NAV_ITEMS[0].href;

  return (
    <Tabs value={activeHref}>
      <TabsList>
        {ADMIN_NAV_ITEMS.map((item) => (
          <TabsTrigger
            key={item.href}
            value={item.href}
            nativeButton={false}
            render={<Link href={item.href} />}
          >
            {item.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}
