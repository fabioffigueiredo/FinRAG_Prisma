import { Composition } from "remotion";
import { PrismaGestorVideo, PrismaLinkedInVideo, PrismaTutorialVideo } from "./VideoPrisma.jsx";
import timingsGestor from "./timings.json";
import timingsLinkedIn from "./timings-linkedin.json";
import timingsTutorial from "./timings-tutorial.json";

const FPS = 30;

export const RemotionRoot = () => {
  return (
    <>
      <Composition
        id="PrismaGestor"
        component={PrismaGestorVideo}
        durationInFrames={timingsGestor.totalFrames + 30}
        fps={FPS}
        width={1920}
        height={1080}
      />
      <Composition
        id="PrismaLinkedIn"
        component={PrismaLinkedInVideo}
        durationInFrames={timingsLinkedIn.totalFrames + 30}
        fps={FPS}
        width={1080}
        height={1920}
      />
      {/* mesmo conteúdo do LinkedIn em quadrado 1:1 (feed desktop + mobile) */}
      <Composition
        id="PrismaSquare"
        component={PrismaLinkedInVideo}
        durationInFrames={timingsLinkedIn.totalFrames + 30}
        fps={FPS}
        width={1080}
        height={1080}
      />
      <Composition
        id="PrismaTutorial"
        component={PrismaTutorialVideo}
        durationInFrames={timingsTutorial.totalFrames + 30}
        fps={FPS}
        width={1920}
        height={1080}
      />
    </>
  );
};
