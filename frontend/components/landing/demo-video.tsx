const YOUTUBE_ID = "TJOCuPYJ0XM";

export function DemoVideo() {
  return (
    <div className="mx-auto w-full max-w-3xl px-6">
      <div className="relative aspect-video w-full overflow-hidden rounded-xl border border-border-strong bg-surface-1">
        <iframe
          className="absolute inset-0 h-full w-full"
          src={`https://www.youtube.com/embed/${YOUTUBE_ID}`}
          title="Janus demo video"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowFullScreen
        />
      </div>
    </div>
  );
}
