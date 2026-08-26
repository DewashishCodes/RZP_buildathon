import Image from "next/image";

/**
 * The Janus mark presented like an ancient coin's relief bust: a duotone
 * ring (verdigris -> copper -> verdigris, the two faces meeting all the
 * way around) framing a dark plate the artwork sits on. The source PNG
 * is a solid near-black silhouette on a transparent background - placed
 * directly on this page's near-black plane it would nearly disappear
 * except for its white linework, so it needs a plate lighter than its
 * own fill to read as a silhouette at all.
 */
export function JanusMedallion({ size = 224 }: { size?: number }) {
  return (
    <div
      className="shrink-0 rounded-full p-[2px]"
      style={{
        width: size,
        height: size,
        background: "conic-gradient(from 180deg, var(--verdigris), var(--copper), var(--verdigris))",
      }}
    >
      <div className="relative flex h-full w-full items-center justify-center overflow-hidden rounded-full bg-surface-2">
        <Image src="/janus-logo.png" alt="Janus" width={size} height={size} className="h-[82%] w-[82%] object-contain" priority />
      </div>
    </div>
  );
}
