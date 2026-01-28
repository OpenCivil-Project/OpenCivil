import { Layout } from "@/components/layout/Layout";
import { motion } from "framer-motion";
import { Box, Eye, Activity, Anchor, Crosshair, ClipboardList } from "lucide-react";
import feature1 from "@/assets/feature-1.png";
import feature2 from "@/assets/feature-2.png";
import feature3 from "@/assets/feature-3.png";
import feature4 from "@/assets/feature-4.png";
import feature6 from "@/assets/feature-6.png";

const features = [
  {
    icon: Box,
    title: "Educational Modeling",
    description: "Render beams as physical shapes (I-beams, T-beams). Supports rigid end offsets, member releases, and cardinal insertion points.",
    image: feature1,
    iconBg: "bg-sky-100",
    iconColor: "text-sky-600",
  },
  {
    icon: Eye,
    title: 'The "Glass Box" Approach',
    description: "Inspect the raw 12x12 Stiffness Matrix [k], Transformation Matrix [T], and FEF vectors for any element. Perfect for education and verification.",
    image: feature2,
    iconBg: "bg-green-100",
    iconColor: "text-green-600",
  },
  {
    icon: Activity,
    title: "Interactive Graphics",
    description: "CAD-like snapping, box selection, and smooth 3D orbiting. Visualizes forces and moments with auto-scaling 3D arrows.",
    image: feature3,
    iconBg: "bg-orange-100",
    iconColor: "text-orange-600",
  },
  {
    icon: Anchor,
    title: "Computed Fixed End Forces",
    description: "Automatically calculates fixed-end moments and shears for various load types on beam elements before analysis begins.",
    image: feature4,
    iconBg: "bg-purple-100",
    iconColor: "text-purple-600",
  },
  {
    icon: Crosshair,
    title: "Exact Deformation Tracking",
    description: "Utilizes high-order shape functions to render precise displacement curves between nodes, accurate right down to the dot.",
    image: feature3,
    iconBg: "bg-red-100",
    iconColor: "text-red-600",
  },
  {
    icon: ClipboardList,
    title: "Detailed Equilibrium Checks",
    description: "Get comprehensive reaction summaries for all supports to ensure global stability and verify that ΣF=0 and ΣM=0.",
    image: feature6,
    iconBg: "bg-cyan-100",
    iconColor: "text-cyan-600",
  },
];

const Features = () => {
  return (
    <Layout>
      <section className="py-24">
        <div className="max-w-7xl mx-auto px-5">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="text-center mb-16"
          >
            <h1 className="text-5xl font-extrabold mb-6">Features</h1>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              A complete toolkit for understanding structural analysis, built from the ground up for transparency and education.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((feature, index) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                className="bg-background border border-border rounded-2xl p-8 transition-all duration-300 hover:-translate-y-2 hover:shadow-xl hover:border-accent group"
              >
                <div className={`w-14 h-14 ${feature.iconBg} ${feature.iconColor} rounded-xl flex items-center justify-center mb-6`}>
                  <feature.icon className="w-7 h-7" />
                </div>
                <h3 className="text-xl font-bold mb-3">{feature.title}</h3>
                <p className="text-muted-foreground text-[0.95rem] mb-6 flex-grow">{feature.description}</p>
                <div className="rounded-lg overflow-hidden border border-border">
                  <img
                    src={feature.image}
                    alt={feature.title}
                    className="w-full h-auto transition-transform duration-500 group-hover:scale-105"
                  />
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>
    </Layout>
  );
};

export default Features;
