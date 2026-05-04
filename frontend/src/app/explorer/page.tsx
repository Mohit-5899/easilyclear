import { redirect } from "next/navigation";

/**
 * Legacy redirect — /explorer was renamed to /library in the 2026-05-02
 * UX redesign. The radial canvas now lives at /library/[subjectSlug]
 * (was [bookSlug] before the 2026-05-04 subject-canonical refactor),
 * with the index at /library.
 */
export default function ExplorerLegacyRedirect() {
  redirect("/library");
}
