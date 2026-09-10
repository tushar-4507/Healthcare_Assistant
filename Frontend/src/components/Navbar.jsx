import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import menu_icon from "../assets/menu_icon.svg";
import cross_icon from "../assets/cross_icon.svg";
import { toast } from "react-toastify";
import { useAuth } from "../context/AuthContext";

const Navbar = ({ solidBackground = false }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const isMainPage = location.pathname === "/main";

  const [showMobileMenu, setShowMobileMenu] = useState(false);
  const [isScrolledPastHome, setIsScrolledPastHome] = useState(false);

  const { user, logout, loading } = useAuth();

  useEffect(() => {
    const handleScroll = () => {
      const homeSection = document.getElementById("Home");
      if (!homeSection) return;
      const rect = homeSection.getBoundingClientRect();
      setIsScrolledPastHome(rect.bottom <= 80);
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    document.body.style.overflow = showMobileMenu ? "hidden" : "auto";
    return () => {
      document.body.style.overflow = "auto";
    };
  }, [showMobileMenu]);

  const isSolid = solidBackground || isScrolledPastHome;

  const handleLogout = async () => {
    try {
      await logout();
      toast.success("Logged out successfully");
      navigate("/");
    } catch {
      toast.error("Logout failed");
    }
  };

  return (
    <div
      className={`fixed top-0 left-0 w-full z-50 transition-all duration-300 ${
        isSolid ? "bg-gray-100 shadow-md" : "bg-transparent"
      }`}
    >
      <div className="w-full flex items-center justify-between py-2 px-6 md:px-20 lg:px-32">
        {/* Logo and Brand */}
        <div className="flex items-center gap-2">
          <a href="/">
            <img
              src="https://static.vecteezy.com/system/resources/previews/015/393/864/non_2x/green-healthcare-logo-design-with-human-life-symbol-illustration-concept-vector.jpg"
              alt="HealthChat Logo"
              className="w-9 h-9 object-cover rounded-full"
            />
          </a>
          <span
            className={`text-xl font-bold ${isSolid ? "text-black" : "text-white"}`}
          >
            <a href="/">Health Chat</a>
          </span>
        </div>

        {/* Desktop Nav Links */}
        <div className="hidden md:flex items-center gap-10">
          <ul
            className={`flex gap-10 font-semibold ${
              isSolid ? "text-black" : "text-white"
            }`}
          >
            <li>
              <a href="/" className="hover:text-gray-500">Home</a>
            </li>
            {!isMainPage && (
              <>
                <li>
                  <a href="#About" className="hover:text-gray-500">About</a>
                </li>
                <li>
                  <a href="#Contact" className="hover:text-gray-500">Contact Us</a>
                </li>
              </>
            )}
          </ul>
          <button
            onClick={user ? handleLogout : () => navigate("/login")}
            className={`px-8 py-2 rounded-full ml-4 transition-all duration-300 ${
              isSolid ? "bg-black text-white" : "bg-white text-black"
            }`}
          >
            {loading ? "..." : user ? "Logout" : "Login"}
          </button>
        </div>

        {/* Mobile Menu Icon */}
        <button
          onClick={() => setShowMobileMenu(true)}
          className={`md:hidden p-2 rounded-md transition-all duration-300 ${
            isSolid ? "bg-gray-300" : "bg-transparent"
          }`}
        >
          <img
            src={menu_icon}
            alt="menu"
            className={`w-6 h-6 transition-all duration-300 ${
              isSolid ? "bg-gray-300" : "bg-transparent"
            }`}
          />
        </button>
      </div>

      {/* Mobile Overlay Menu */}
      <div
        className={`fixed top-0 right-0 w-full h-full bg-white z-40 transform transition-transform duration-300 ${
          showMobileMenu ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex justify-end p-6">
          <button onClick={() => setShowMobileMenu(false)}>
            <img src={cross_icon} alt="close" className="w-6" />
          </button>
        </div>
        <ul className="flex flex-col items-center gap-6 mt-10 text-lg font-semibold text-black">
          <li>
            <a
              onClick={() => setShowMobileMenu(false)}
              href="/"
              className="px-4 py-2 rounded-full"
            >
              Home
            </a>
          </li>
          {!isMainPage && (
            <>
              <li>
                <a
                  onClick={() => setShowMobileMenu(false)}
                  href="#About"
                  className="px-4 py-2 rounded-full"
                >
                  About
                </a>
              </li>
              <li>
                <a
                  onClick={() => setShowMobileMenu(false)}
                  href="#Contact"
                  className="px-4 py-2 rounded-full"
                >
                  Contact Us
                </a>
              </li>
            </>
          )}
          <button
            onClick={user ? handleLogout : () => navigate("/login")}
            className="bg-black text-white px-8 py-2 rounded-full mt-4"
          >
            {loading ? "..." : user ? "Logout" : "Login"}
          </button>
        </ul>
      </div>
    </div>
  );
};

export default Navbar;
