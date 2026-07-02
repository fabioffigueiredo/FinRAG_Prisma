import { Composition } from "remotion";
import { PrismaGestorVideo, PrismaLinkedInVideo } from "./VideoPrisma.jsx";
import timingsGestor from "./timings.json";
import timingsLinkedIn from "./timings-linkedin.json";

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
    </>
  );
};
