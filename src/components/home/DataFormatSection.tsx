import { motion } from "framer-motion";
import { FileJson, Code, Shield } from "lucide-react";

const benefits = [
  {
    icon: Code,
    title: "Easy Parsing",
    description: "Load models directly into Python, MATLAB, or Excel.",
  },
  {
    icon: FileJson,
    title: "Transparent Structure",
    description: "Every node, element, and load is clearly defined.",
  },
  {
    icon: Shield,
    title: "Future Proof",
    description: "Your data belongs to you, forever accessible.",
  },
];

// Syntax highlighting components
const JsonKey = ({ children }: { children: React.ReactNode }) => (
  <span className="text-purple-400">{children}</span>
);

const JsonString = ({ children }: { children: React.ReactNode }) => (
  <span className="text-green-400">{children}</span>
);

const JsonNumber = ({ children }: { children: React.ReactNode }) => (
  <span className="text-orange-300">{children}</span>
);

const JsonBool = ({ children }: { children: React.ReactNode }) => (
  <span className="text-pink-400">{children}</span>
);

const PyKeyword = ({ children }: { children: React.ReactNode }) => (
  <span className="text-pink-400">{children}</span>
);

const PyFunc = ({ children }: { children: React.ReactNode }) => (
  <span className="text-blue-400">{children}</span>
);

const PyString = ({ children }: { children: React.ReactNode }) => (
  <span className="text-green-400">{children}</span>
);

const PyComment = ({ children }: { children: React.ReactNode }) => (
  <span className="text-slate-500">{children}</span>
);

const PySelf = ({ children }: { children: React.ReactNode }) => (
  <span className="text-purple-400">{children}</span>
);

function JsonCodeBlock() {
  return (
    <pre className="p-5 text-sm font-mono text-slate-300 overflow-x-auto">
      <code>
{`{`}
{"\n"}  <JsonKey>"info"</JsonKey>: {"{"} <JsonKey>"name"</JsonKey>: <JsonString>"Project 1"</JsonString>, <JsonKey>"units"</JsonKey>: <JsonString>"kN, m, C"</JsonString> {"}"},
{"\n"}  <JsonKey>"materials"</JsonKey>: [
{"\n"}    {"{"} <JsonKey>"name"</JsonKey>: <JsonString>"Steel"</JsonString>, <JsonKey>"E"</JsonKey>: <JsonNumber>2.0e+11</JsonNumber>, <JsonKey>"rho"</JsonKey>: <JsonNumber>7850.0</JsonNumber> {"}"}
{"\n"}  ],
{"\n"}  <JsonKey>"elements"</JsonKey>: [
{"\n"}    {"{"}
{"\n"}      <JsonKey>"id"</JsonKey>: <JsonNumber>1</JsonNumber>,
{"\n"}      <JsonKey>"n1_id"</JsonKey>: <JsonNumber>1</JsonNumber>, <JsonKey>"n2_id"</JsonKey>: <JsonNumber>2</JsonNumber>,
{"\n"}      <JsonKey>"sec_name"</JsonKey>: <JsonString>"IPE300"</JsonString>,
{"\n"}      <JsonKey>"rel_i"</JsonKey>: [<JsonBool>false</JsonBool>, <JsonBool>false</JsonBool>, <JsonBool>false</JsonBool>, <JsonBool>false</JsonBool>, <JsonBool>false</JsonBool>, <JsonBool>false</JsonBool>]
{"\n"}    {"}"}
{"\n"}  ]
{"\n"}{`}`}
      </code>
    </pre>
  );
}

function PythonCodeBlock() {
  return (
    <pre className="p-5 text-sm font-mono text-slate-300 overflow-x-auto">
      <code><PyKeyword>class</PyKeyword> <PyFunc>LinearSolver</PyFunc>:
{"\n"}    <PyKeyword>def</PyKeyword> <PyFunc>solve</PyFunc>(<PySelf>self</PySelf>):
{"\n"}        <PyComment># Executes the linear algebra solution: K_ff * U_f = P_f</PyComment>
{"\n"}        <PyFunc>print</PyFunc>(<PyString>"Solver: Applying Boundary Conditions..."</PyString>)
{"\n"}        
{"\n"}        <PyComment># 1. Partition the System (Sparse CSC)</PyComment>
{"\n"}        K_csc = <PySelf>self</PySelf>.K.<PyFunc>tocsc</PyFunc>()
{"\n"}        K_ff = K_csc[is_free, :][:, is_free]
{"\n"}        P_f = <PySelf>self</PySelf>.P[is_free]
{"\n"}
{"\n"}        <PyComment># 2. Solve (The "Big Math")</PyComment>
{"\n"}        <PyKeyword>try</PyKeyword>:
{"\n"}            U_f = <PyFunc>solve_sparse</PyFunc>(K_ff, P_f) <PyComment># Optimized Solver</PyComment>
{"\n"}        <PyKeyword>except</PyKeyword> (<PyFunc>RuntimeError</PyFunc>, <PyFunc>ValueError</PyFunc>) <PyKeyword>as</PyKeyword> e:
{"\n"}            <PyComment># ERROR CHECK E301: Singular Matrix</PyComment>
{"\n"}            <PyKeyword>raise</PyKeyword> <PyFunc>SolverException</PyFunc>(<PyString>"E301"</PyString>, <PyFunc>str</PyFunc>(e))
{"\n"}
{"\n"}        <PyKeyword>return</PyKeyword> U_f, <PySelf>self</PySelf>.Reactions</code>
    </pre>
  );
}

export function DataFormatSection() {
  return (
    <section className="py-24 bg-muted/30">
      <div className="max-w-7xl mx-auto px-5">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl font-extrabold mb-4">Human-Readable Data Format</h2>
          <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
            No proprietary binary blobs. Open Civil uses simple, transparent JSON files (.mf) that you can read, edit, or generate with Python scripts.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-6 mb-12">
          {benefits.map((benefit, index) => (
            <motion.div
              key={benefit.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              viewport={{ once: true }}
              className="flex items-start gap-4 p-6 bg-background border border-border rounded-xl"
            >
              <div className="w-10 h-10 bg-accent/10 text-accent rounded-lg flex items-center justify-center flex-shrink-0">
                <benefit.icon className="w-5 h-5" />
              </div>
              <div>
                <h4 className="font-bold mb-1">{benefit.title}</h4>
                <p className="text-muted-foreground text-sm">{benefit.description}</p>
              </div>
            </motion.div>
          ))}
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5 }}
            viewport={{ once: true }}
            className="bg-[#1e1e2e] rounded-xl overflow-hidden border border-border"
          >
            <div className="flex items-center justify-between px-4 py-3 bg-[#181825] border-b border-border">
              <div className="flex items-center gap-2">
                <FileJson className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground font-mono">test1.mf</span>
              </div>
              <div className="flex gap-1.5">
                <span className="w-3 h-3 rounded-full bg-red-500/80"></span>
                <span className="w-3 h-3 rounded-full bg-yellow-500/80"></span>
                <span className="w-3 h-3 rounded-full bg-green-500/80"></span>
              </div>
            </div>
            <JsonCodeBlock />
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5 }}
            viewport={{ once: true }}
            className="bg-[#1e1e2e] rounded-xl overflow-hidden border border-border"
          >
            <div className="flex items-center justify-between px-4 py-3 bg-[#181825] border-b border-border">
              <div className="flex items-center gap-2">
                <Code className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground font-mono">core/solver_kernel.py</span>
              </div>
              <div className="flex gap-1.5">
                <span className="w-3 h-3 rounded-full bg-red-500/80"></span>
                <span className="w-3 h-3 rounded-full bg-yellow-500/80"></span>
                <span className="w-3 h-3 rounded-full bg-green-500/80"></span>
              </div>
            </div>
            <PythonCodeBlock />
          </motion.div>
        </div>
      </div>
    </section>
  );
}
