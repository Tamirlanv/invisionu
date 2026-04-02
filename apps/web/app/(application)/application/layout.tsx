import type { Metadata } from "next";
import { ApplicationShell } from "@/components/application/ApplicationShell";

export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default function ApplicationLayout({ children }: { children: React.ReactNode }) {
  return <ApplicationShell>{children}</ApplicationShell>;
}
