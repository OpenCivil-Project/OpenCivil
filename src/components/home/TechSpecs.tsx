import { motion } from "framer-motion";
import { Play, Search, CheckCircle } from "lucide-react";

const benefits = [
  {
    icon: Play,
    title: "Watch It Move",
    description: "See your structure deform under load with smooth, real-time animations. No guesswork—just visual clarity.",
    gradient: "from-sky-500 to-blue-600",
  },
  {
    icon: Search,
    title: "Understand the Math",
    description: "Peek inside the solver. View stiffness matrices, transformation matrices, and fixed-end forces for any element.",
    gradient: "from-emerald-500 to-green-600",
  },
  {
    icon: CheckCircle,
    title: "Verify Your Results",
    description: "Get detailed equilibrium checks and reaction summaries. Confirm that ΣF=0 and ΣM=0 with confidence.",
    gradient: "from-amber-500 to-orange-600",
  },
];

export function TechSpecs() {
  return (
    <section className="py-24">
      <div className="max-w-7xl mx-auto px-5">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          viewport={{ once: true }}
          className="text-center mb-12"
        >
          <h2 className="text-3xl font-bold mb-4">Why OpenCivil?</h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            Built for students and engineers who want to truly understand structural behavior.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-8">
          {benefits.map((benefit, index) => (
            <motion.div
              key={benefit.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              viewport={{ once: true }}
              className="bg-background border border-border rounded-2xl p-8 text-center hover:shadow-xl hover:border-accent transition-all duration-300 hover:-translate-y-1"
            >
              <div className={`w-16 h-16 mx-auto mb-6 rounded-2xl bg-gradient-to-br ${benefit.gradient} flex items-center justify-center shadow-lg`}>
                <benefit.icon className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-xl font-bold mb-3">{benefit.title}</h3>
              <p className="text-muted-foreground text-[0.95rem] leading-relaxed">
                {benefit.description}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
