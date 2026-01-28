import { Layout } from "@/components/layout/Layout";
import { motion } from "framer-motion";
import { MapPin, Mail, GraduationCap, Code2, Cpu, Building2, Download } from "lucide-react";
import { Button } from "@/components/ui/button";

const projects = [
  {
    title: "OpenCivil",
    role: "Creator & Lead Developer",
    year: "2024 – Present",
    description: "Architected a professional-grade FEA software from scratch, decoupling the high-performance physics kernel from the frontend using MVC architecture. Engineered a custom 3D OpenGL graphics engine.",
    icon: Code2,
  },
  {
    title: "CE-Star: Computational Seismic Analysis",
    role: "Research & Lead Developer",
    year: "Ongoing",
    description: "Multi-threaded ETL pipeline for earthquake data, custom NLTHA solver with Newmark-β integration, and automated LaTeX report generation.",
    icon: Cpu,
  },
];

const experience = [
  {
    company: "Parabol Yazılım (METU Technopolis)",
    role: "Urban Mobility Intern",
    period: "Jul 2025 – Aug 2025",
    location: "Ankara, Turkey",
  },
  {
    company: "DSI – State Hydraulic Works",
    role: "Civil Engineering Intern (Dams Department)",
    period: "Aug 2025 – Sep 2025",
    location: "Ankara, Turkey",
  },
];

const About = () => {
  return (
    <Layout>
      <section className="py-24">
        <div className="max-w-5xl mx-auto px-5">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="text-center mb-16"
          >
            <h1 className="text-5xl font-extrabold mb-4">Shaikh Ahmed Azad</h1>
            <p className="text-xl text-muted-foreground mb-6">
              Civil Engineering Student — Computational Structural & Earthquake Engineering
            </p>
            <div className="flex flex-wrap justify-center gap-4 text-sm text-muted-foreground mb-6">
              <span className="flex items-center gap-2">
                <MapPin className="w-4 h-4 text-accent" />
                Ankara, Turkey
              </span>
              <span className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-accent" />
                ahmed.azad@metu.edu.tr
              </span>
              <span className="flex items-center gap-2">
                <GraduationCap className="w-4 h-4 text-accent" />
                METU, 4th Year
              </span>
            </div>
            <Button asChild size="lg" className="gap-2">
              <a href="/CV4.pdf" download>
                <Download className="w-4 h-4" />
                Download CV
              </a>
            </Button>
          </motion.div>

          {/* Education */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="mb-16"
          >
            <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
              <GraduationCap className="w-6 h-6 text-accent" />
              Education
            </h2>
            <div className="bg-muted/50 rounded-xl p-6 border border-border">
              <h3 className="text-lg font-bold">Middle East Technical University (METU)</h3>
              <p className="text-muted-foreground">B.Sc. Civil Engineering (4th Year)</p>
              <p className="text-sm text-muted-foreground mt-1">Oct 2022 – Present • Ankara, Turkey</p>
            </div>
          </motion.div>

          {/* Projects */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="mb-16"
          >
            <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
              <Code2 className="w-6 h-6 text-accent" />
              Computational Engineering Projects
            </h2>
            <div className="space-y-6">
              {projects.map((project) => (
                <div key={project.title} className="bg-muted/50 rounded-xl p-6 border border-border">
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 bg-accent/10 text-accent rounded-xl flex items-center justify-center flex-shrink-0">
                      <project.icon className="w-6 h-6" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold">{project.title}</h3>
                      <p className="text-sm text-accent font-medium">{project.role} • {project.year}</p>
                      <p className="text-muted-foreground mt-2 text-[0.95rem]">{project.description}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Experience */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.4 }}
          >
            <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
              <Building2 className="w-6 h-6 text-accent" />
              Professional Experience
            </h2>
            <div className="space-y-4">
              {experience.map((exp) => (
                <div key={exp.company} className="bg-muted/50 rounded-xl p-6 border border-border">
                  <h3 className="font-bold">{exp.company}</h3>
                  <p className="text-accent font-medium text-sm">{exp.role}</p>
                  <p className="text-muted-foreground text-sm mt-1">{exp.period} • {exp.location}</p>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>
    </Layout>
  );
};

export default About;
