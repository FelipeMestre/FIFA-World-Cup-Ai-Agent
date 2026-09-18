import { HomeShell } from "@/features/chat/components/home-shell";

/**
 * Public home page — accessible at /home without authentication.
 * Renders the HomeActive design: hero, composer, suggested prompts.
 * No auth check — intentionally open for landing/marketing purposes.
 */
export default function HomePage() {
  return <HomeShell />;
}