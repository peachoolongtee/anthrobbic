import { FlyIn } from "@/components/landing/fly-in";
import { Overview } from "@/components/overview/overview";

/** The website opens on the overview, after the plane crosses the screen. */
export default function Home() {
  return (
    <>
      <FlyIn />
      <Overview />
    </>
  );
}
