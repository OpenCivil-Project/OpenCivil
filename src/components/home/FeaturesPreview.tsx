import { motion } from "framer-motion";
import { Box, Eye, Activity, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import feature1 from "@/assets/feature-1.png";
import feature2 from "@/assets/feature-2.png";
import feature3 from "@/assets/feature-3.png";

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
];

export function FeaturesPreview() {
  return (
    <section className="py-24 bg-muted/50">
      <div className="max-w-7xl mx-auto px-5">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-extrabold mb-4">Powerful Features</h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Built for students and researchers who want to understand structural analysis from the ground up.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 mb-12">
          {features.map((feature, index) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              viewport={{ once: true }}
              className="bg-background border border-border rounded-2xl p-8 transition-all duration-300 hover:-translate-y-2 hover:shadow-xl hover:border-accent group"
            >
              <div className={`w-14 h-14 ${feature.iconBg} ${feature.iconColor} rounded-xl flex items-center justify-center mb-6`}>
                <feature.icon className="w-7 h-7" />
              </div>
              <h3 className="text-xl font-bold mb-3">{feature.title}</h3>
              <p className="text-muted-foreground text-[0.95rem] mb-6">{feature.description}</p>
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

        <div className="text-center">
          <Button size="lg" variant="outline" asChild>
            <Link to="/features">
              See All Features
              <ArrowRight className="w-5 h-5 ml-2" />
            </Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
