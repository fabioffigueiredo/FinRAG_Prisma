"use client";

import { useRouter } from "next/navigation";
import { TotpEnrollment } from "@/components/app/totp-enrollment";

export function AtivarDoisFatoresShell() {
  const router = useRouter();

  function onAtivado() {
    router.push("/");
    router.refresh();
  }

  return <TotpEnrollment onAtivado={onAtivado} />;
}
