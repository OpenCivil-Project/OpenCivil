import { Link, useLocation } from "react-router-dom";
import { Box, Github, Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useState } from "react";
const navLinks = [{
  href: "/",
  label: "Home"
}, {
  href: "/features",
  label: "Features"
}, {
  href: "/showcase",
  label: "Showcase"
}, {
  href: "/about",
  label: "About"
}, {
  href: "/contact",
  label: "Contact"
}];
export function Navbar() {
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  return <nav className="fixed top-0 w-full bg-background/90 backdrop-blur-xl z-50 border-b border-border">
      <div className="max-w-7xl mx-auto px-5 h-[72px] flex justify-between items-center">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2.5 font-extrabold text-xl text-foreground">
          <Box className="w-6 h-6 text-accent" />
          <span>Open Civil</span>
        </Link>

        {/* Desktop Nav Links */}
        <ul className="hidden md:flex gap-8 list-none">
          {navLinks.map(link => <li key={link.href}>
              <Link to={link.href} className={`text-[0.95rem] font-medium transition-colors ${location.pathname === link.href ? "text-foreground" : "text-muted-foreground hover:text-foreground"}`}>
                {link.label}
              </Link>
            </li>)}
        </ul>

        {/* Desktop Actions */}
        <div className="hidden md:flex gap-5 items-center">
          <a href="https://github.com/ShaikhAhmedAzad/OpenCivil" target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 text-secondary-foreground font-semibold hover:text-foreground transition-colors opacity-80">
            <Github className="w-5 h-5" />
            GitHub
          </a>
          <Button asChild>
            <a href="https://github.com/ShaikhAhmedAzad/OpenCivil/releases/latest" target="_blank" rel="noopener noreferrer">
              Download v0.51
            </a>
          </Button>
        </div>

        {/* Mobile Menu Button */}
        <button className="md:hidden p-2" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
          {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Mobile Menu */}
      {mobileMenuOpen && <div className="md:hidden bg-background border-b border-border px-5 py-4">
          <ul className="flex flex-col gap-4">
            {navLinks.map(link => <li key={link.href}>
                <Link to={link.href} onClick={() => setMobileMenuOpen(false)} className={`block text-base font-medium ${location.pathname === link.href ? "text-foreground" : "text-muted-foreground"}`}>
                  {link.label}
                </Link>
              </li>)}
          </ul>
          <div className="mt-4 flex flex-col gap-3">
            <a href="https://github.com/ShaikhAhmedAzad/OpenCivil" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-muted-foreground font-semibold">
              <Github className="w-5 h-5" />
              GitHub
            </a>
            <Button asChild className="w-full">
              <a href="https://github.com/ShaikhAhmedAzad/OpenCivil/releases/latest" target="_blank" rel="noopener noreferrer">
                Download v0.51
              </a>
            </Button>
          </div>
        </div>}
    </nav>;
}