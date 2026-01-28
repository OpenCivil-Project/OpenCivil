import { Layout } from "@/components/layout/Layout";
import { useEffect, useRef } from "react";
import { Play } from "lucide-react";

interface VideoCardProps {
  src: string;
  title: string;
  description: string;
}

function VideoCard({ src, title, description }: VideoCardProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const video = videoRef.current;
    const container = containerRef.current;
    if (!video || !container) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            video.play().catch(() => {
              // Autoplay blocked - user interaction required
            });
          } else {
            video.pause();
          }
        });
      },
      { threshold: 0.5 }
    );

    observer.observe(container);

    return () => observer.disconnect();
  }, []);

  return (
    <div 
      ref={containerRef}
      className="group relative bg-card rounded-2xl overflow-hidden border border-border shadow-xl hover:shadow-2xl transition-shadow duration-300"
    >
      <div className="relative aspect-[16/10] bg-slate-900">
        <video
          ref={videoRef}
          src={src}
          muted
          loop
          playsInline
          className="w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        <div className="absolute bottom-4 left-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
          <div className="flex items-center gap-2 text-white/80 text-sm">
            <Play className="w-4 h-4" />
            <span>Auto-playing</span>
          </div>
        </div>
      </div>
      <div className="p-5">
        <h3 className="text-lg font-bold text-foreground mb-2">{title}</h3>
        <p className="text-muted-foreground text-sm">{description}</p>
      </div>
    </div>
  );
}

const SUPABASE_URL = "https://zizmttgmketyuoerainb.supabase.co";

const videos = [
  {
    src: `${SUPABASE_URL}/storage/v1/object/public/videos/Deformed%20Shape%20and%20Animation2.mp4`,
    title: "General Interface Overview",
    description: "Explore OpenCivil's intuitive interface for structural modeling, analysis setup, and real-time visualization controls."
  },
  {
    src: `${SUPABASE_URL}/storage/v1/object/public/videos/Deformed%20Shape%20and%20Animation.mp4`,
    title: "Deformed Shape Animation",
    description: "Visualization of structural deformation under applied loads, showing displacement magnification for clarity."
  },
  {
    src: `${SUPABASE_URL}/storage/v1/object/public/videos/Modal%20Analysis%20Animation.mp4`,
    title: "Modal Analysis Animation",
    description: "Dynamic modal analysis showing natural frequencies and mode shapes of the structural system."
  },
  {
    src: `${SUPABASE_URL}/storage/v1/object/public/videos/Modal%20Analysis%20and%20%20Modal%20Table.mp4`,
    title: "Modal Analysis & Data Tables",
    description: "Animated mode shapes with corresponding modal data tables displaying frequencies, mass participation, and structural properties."
  },
];

const Showcase = () => {
  return (
    <Layout>
      <section className="py-20 md:py-28">
        <div className="max-w-7xl mx-auto px-5">
          {/* Header */}
          <div className="text-center mb-16">
            <span className="inline-block px-4 py-1.5 bg-accent/10 text-accent text-sm font-semibold rounded-full mb-4">
              Showcase
            </span>
            <h1 className="text-4xl md:text-5xl font-extrabold text-foreground mb-4">
              See OpenCivil in Action
            </h1>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              Watch real-time structural analysis demonstrations, deformed shape animations, 
              and solver visualizations powered by OpenCivil's FEA engine.
            </p>
          </div>

          {/* Video Grid - 2 columns */}
          <div className="grid gap-8 md:grid-cols-2 max-w-7xl mx-auto">
            {videos.map((video, index) => (
              <VideoCard
                key={index}
                src={video.src}
                title={video.title}
                description={video.description}
              />
            ))}
          </div>

          {/* Active Development Notice */}
          <div className="mt-12 text-center">
            <p className="text-muted-foreground text-sm">
              More demonstrations coming soon... Actively being developed
            </p>
          </div>
        </div>
      </section>
    </Layout>
  );
};

export default Showcase;
