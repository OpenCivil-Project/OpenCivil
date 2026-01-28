import { motion } from "framer-motion";
import { Github, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
export function CTASection() {
  const handleCopy = () => {
    navigator.clipboard.writeText("git clone https://github.com/ShaikhAhmedAzad/OpenCivil.git");
    toast.success("Copied to clipboard!");
  };
  return <section className="py-24">
      <div className="max-w-7xl mx-auto px-5">
        <motion.div initial={{
        opacity: 0,
        y: 20
      }} whileInView={{
        opacity: 1,
        y: 0
      }} transition={{
        duration: 0.5
      }} viewport={{
        once: true
      }} className="bg-primary text-primary-foreground rounded-3xl p-12 lg:p-20 grid lg:grid-cols-[1.5fr_1fr] gap-12 items-center" style={{
        backgroundImage: "radial-gradient(circle at top right, hsl(217 33% 17%) 0%, hsl(var(--primary)) 60%)"
      }}>
          <div>
            <h2 className="text-3xl lg:text-4xl font-extrabold mb-4 text-secondary-foreground">Ready to start analyzing?</h2>
            <p className="text-primary-foreground/70 text-lg mb-6">
              Open Civil is open-source and free to use. Contribute to the project or use it for your research.
            </p>
            
            <div className="bg-black/30 p-4 rounded-lg border border-white/10 flex justify-between items-center mb-8 font-mono text-sm">
              <code>git clone https://github.com/ShaikhAhmedAzad/OpenCivil.git</code>
              <button onClick={handleCopy} className="text-primary-foreground/60 hover:text-primary-foreground transition-colors ml-4">
                <Copy className="w-5 h-5" />
              </button>
            </div>
            
            <div className="flex flex-wrap gap-4">
              <Button variant="secondary" size="lg" asChild className="bg-white text-primary hover:bg-white/90">
                <a href="https://github.com/ShaikhAhmedAzad/OpenCivil" target="_blank" rel="noopener noreferrer">
                  <Github className="w-5 h-5 mr-2" />
                  View on GitHub
                </a>
              </Button>
              <Button variant="outline" size="lg" className="border-white/20 text-primary-foreground hover:bg-white/5 hover:border-white" asChild>
                <a href="https://github.com/ShaikhAhmedAzad/OpenCivil#readme" target="_blank" rel="noopener noreferrer" className="text-secondary">
                  Read Documentation
                </a>
              </Button>
            </div>
          </div>
          
          <div>
            <h4 className="text-primary-foreground/80 font-mono font-semibold mb-4">{">_"} System Requirements</h4>
            <ul className="space-y-3">
              {["OS: Windows, macOS, or Linux", "Python 3.10 or higher", "RAM: 4GB Minimum (8GB Rec)", "OpenGL 3.3+ Compatible GPU"].map(req => <li key={req} className="flex gap-3 text-primary-foreground/70 text-[0.95rem]">
                  <span className="text-green-400 font-mono font-bold">{">"}</span>
                  {req}
                </li>)}
            </ul>
          </div>
        </motion.div>
      </div>
    </section>;
}