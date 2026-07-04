import { Sidebar } from "@/components/app/sidebar";
import { Topbar } from "@/components/app/topbar";
import { BackendProvider } from "@/components/app/backend-context";
import { FundProvider } from "@/components/app/fund-context";
import { MotionProvider } from "@/components/app/motion-provider";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <MotionProvider>
      <BackendProvider>
        <FundProvider>
          <div className="flex min-h-dvh">
            <Sidebar />
            <div className="flex min-w-0 flex-1 flex-col">
              <Topbar />
              <main className="flex-1 px-4 py-6 md:px-8 md:py-8">{children}</main>
            </div>
          </div>
        </FundProvider>
      </BackendProvider>
    </MotionProvider>
  );
}
