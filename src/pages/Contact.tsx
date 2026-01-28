import { Layout } from "@/components/layout/Layout";
import { motion } from "framer-motion";
import { Mail, MessageSquare, Rocket, Github, MapPin, Phone } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useState } from "react";
import { toast } from "sonner";

const Contact = () => {
  const [contactForm, setContactForm] = useState({ name: "", email: "", message: "" });
  const [waitlistEmail, setWaitlistEmail] = useState("");
  const [isContactSubmitting, setIsContactSubmitting] = useState(false);
  const [isWaitlistSubmitting, setIsWaitlistSubmitting] = useState(false);

  const handleContactSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsContactSubmitting(true);
    
    // TODO: Connect to Lovable Cloud database
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    toast.success("Message sent! I'll get back to you soon.");
    setContactForm({ name: "", email: "", message: "" });
    setIsContactSubmitting(false);
  };

  const handleWaitlistSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsWaitlistSubmitting(true);
    
    // TODO: Connect to Lovable Cloud database
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    toast.success("You're on the waitlist! We'll notify you of updates.");
    setWaitlistEmail("");
    setIsWaitlistSubmitting(false);
  };

  return (
    <Layout>
      <section className="py-24">
        <div className="max-w-6xl mx-auto px-5">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="text-center mb-16"
          >
            <h1 className="text-5xl font-extrabold mb-4">Get in Touch</h1>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              Have questions about Open Civil? Want to collaborate on structural engineering research? I'd love to hear from you.
            </p>
          </motion.div>

          <div className="grid lg:grid-cols-2 gap-12">
            {/* Contact Form */}
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="bg-background border border-border rounded-2xl p-8"
            >
              <div className="flex items-center gap-3 mb-6">
                <div className="w-12 h-12 bg-accent/10 text-accent rounded-xl flex items-center justify-center">
                  <MessageSquare className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-xl font-bold">Send a Message</h2>
                  <p className="text-sm text-muted-foreground">I'll respond within 24-48 hours</p>
                </div>
              </div>

              <form onSubmit={handleContactSubmit} className="space-y-5">
                <div>
                  <Label htmlFor="name">Name</Label>
                  <Input
                    id="name"
                    placeholder="Your name"
                    value={contactForm.name}
                    onChange={(e) => setContactForm({ ...contactForm, name: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="your@email.com"
                    value={contactForm.email}
                    onChange={(e) => setContactForm({ ...contactForm, email: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="message">Message</Label>
                  <Textarea
                    id="message"
                    placeholder="Your message..."
                    rows={5}
                    value={contactForm.message}
                    onChange={(e) => setContactForm({ ...contactForm, message: e.target.value })}
                    required
                  />
                </div>
                <Button type="submit" className="w-full" disabled={isContactSubmitting}>
                  {isContactSubmitting ? "Sending..." : "Send Message"}
                </Button>
              </form>
            </motion.div>

            {/* Waitlist & Contact Info */}
            <div className="space-y-8">
              {/* Waitlist */}
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5, delay: 0.2 }}
                className="bg-primary text-primary-foreground rounded-2xl p-8"
                style={{
                  backgroundImage: "radial-gradient(circle at top right, hsl(217 33% 17%) 0%, hsl(var(--primary)) 60%)",
                }}
              >
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-12 h-12 bg-white/10 rounded-xl flex items-center justify-center">
                    <Rocket className="w-6 h-6" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold">Join the Waitlist</h2>
                    <p className="text-sm text-primary-foreground/70">Get notified about updates & new features</p>
                  </div>
                </div>

                <form onSubmit={handleWaitlistSubmit} className="flex gap-3">
                  <Input
                    type="email"
                    placeholder="your@email.com"
                    value={waitlistEmail}
                    onChange={(e) => setWaitlistEmail(e.target.value)}
                    required
                    className="bg-white/10 border-white/20 text-primary-foreground placeholder:text-primary-foreground/50"
                  />
                  <Button type="submit" variant="secondary" className="bg-white text-primary hover:bg-white/90" disabled={isWaitlistSubmitting}>
                    {isWaitlistSubmitting ? "..." : "Join"}
                  </Button>
                </form>
              </motion.div>

              {/* Contact Info */}
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5, delay: 0.3 }}
                className="bg-muted/50 border border-border rounded-2xl p-8"
              >
                <h2 className="text-xl font-bold mb-6">Contact Information</h2>
                <div className="space-y-4">
                  <a
                    href="mailto:ahmed.azad@metu.edu.tr"
                    className="flex items-center gap-4 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <div className="w-10 h-10 bg-accent/10 text-accent rounded-lg flex items-center justify-center">
                      <Mail className="w-5 h-5" />
                    </div>
                    <span>ahmed.azad@metu.edu.tr</span>
                  </a>
                  <div className="flex items-center gap-4 text-muted-foreground">
                    <div className="w-10 h-10 bg-accent/10 text-accent rounded-lg flex items-center justify-center">
                      <Phone className="w-5 h-5" />
                    </div>
                    <span>+90 534 491 1235</span>
                  </div>
                  <div className="flex items-center gap-4 text-muted-foreground">
                    <div className="w-10 h-10 bg-accent/10 text-accent rounded-lg flex items-center justify-center">
                      <MapPin className="w-5 h-5" />
                    </div>
                    <span>Ankara, Turkey</span>
                  </div>
                  <a
                    href="https://github.com/ShaikhAhmedAzad/OpenCivil"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-4 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <div className="w-10 h-10 bg-accent/10 text-accent rounded-lg flex items-center justify-center">
                      <Github className="w-5 h-5" />
                    </div>
                    <span>github.com/ShaikhAhmedAzad/OpenCivil</span>
                  </a>
                </div>
              </motion.div>
            </div>
          </div>
        </div>
      </section>
    </Layout>
  );
};

export default Contact;
