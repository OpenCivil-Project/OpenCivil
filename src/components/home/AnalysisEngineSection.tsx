import { motion } from "framer-motion";
import { Calculator, Grid3X3, AlertTriangle, Cpu } from "lucide-react";

const features = [
  {
    icon: Calculator,
    title: "Mathematical Formulation",
    description: "Implements Timoshenko Beam Theory accounting for shear deformation. Accurate for both slender and deep beams.",
  },
  {
    icon: Grid3X3,
    title: "Advanced Matrix Operations",
    description: "Static condensation for member releases. Transformation matrices for rigid zones, offsets, and cardinal insertion points.",
  },
  {
    icon: AlertTriangle,
    title: "Smart Error Handling",
    description: "Diagnoses singular matrices (E301), zero-length elements (E201), and missing properties instead of just crashing.",
  },
];

export function AnalysisEngineSection() {
  return (
    <section className="py-24">
      <div className="max-w-7xl mx-auto px-5">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5 }}
            viewport={{ once: true }}
          >
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 bg-accent/10 text-accent rounded-xl flex items-center justify-center">
                <Cpu className="w-6 h-6" />
              </div>
              <h2 className="text-4xl font-extrabold">The Analysis Engine</h2>
            </div>
            <p className="text-lg text-muted-foreground mb-10">
              A standalone, high-performance Python engine that strictly separates physics from UI.
            </p>

            <div className="space-y-6">
              {features.map((feature, index) => (
                <motion.div
                  key={feature.title}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: index * 0.1 }}
                  viewport={{ once: true }}
                  className="flex gap-4 p-5 bg-muted/30 border border-border rounded-xl hover:border-accent/50 transition-colors"
                >
                  <div className="w-10 h-10 bg-background border border-border text-accent rounded-lg flex items-center justify-center flex-shrink-0">
                    <feature.icon className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="font-bold mb-1">{feature.title}</h4>
                    <p className="text-muted-foreground text-sm">{feature.description}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5 }}
            viewport={{ once: true }}
            className="relative"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-accent/20 to-transparent rounded-3xl blur-3xl"></div>
            <div className="relative bg-[#1e293b] rounded-2xl overflow-hidden border border-border shadow-2xl">
              <div className="flex items-center gap-2 px-4 py-3 bg-[#0f172a] border-b border-border">
                <div className="flex gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-red-500/80"></span>
                  <span className="w-3 h-3 rounded-full bg-yellow-500/80"></span>
                  <span className="w-3 h-3 rounded-full bg-green-500/80"></span>
                </div>
                <span className="text-sm text-muted-foreground font-mono ml-2">solver_kernel.py</span>
              </div>
              <pre className="p-6 text-sm font-mono text-slate-300 overflow-x-auto leading-relaxed">
                <code>{`def assemble_global_stiffness(self):
    """
    Assembles K_global from element matrices.
    Applies coordinate transformations.
    """
    for elem in self.elements:
        # Get local stiffness matrix
        k_local = elem.get_stiffness_matrix()
        
        # Transform to global coordinates
        T = elem.get_transformation_matrix()
        k_global = T.T @ k_local @ T
        
        # Apply static condensation if releases
        if elem.has_releases:
            k_global = self.condense(k_global, elem)
        
        # Scatter into global matrix
        self.K[dofs, dofs] += k_global
    
    return self.K  # Sparse CSC format`}</code>
              </pre>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
