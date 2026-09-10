import React from "react";
import Navbar from "../components/Navbar";
import { motion } from "motion/react";
import right_arrow from "../assets/right_arrow.svg";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { useAuth } from "../context/AuthContext";

const Home = () => {
  const navigate = useNavigate();
  const { user, loading } = useAuth();

  const handleClick = () => {
    if (loading) return;
    if (!user) {
      toast.info("Please login first");
      navigate("/login");
      return;
    }

    setTimeout(() => {
      navigate("/main");
    }, 200);
  };

  return (
    <div
      className="min-h-screen bg-cover bg-center w-full overflow-hidden"
      style={{
        backgroundImage:
          "url('https://img.freepik.com/premium-vector/abstract-circle-digital-cyber-security-fingerprint-connection-communication-futuristic-blue-background_36402-1388.jpg')",
      }}
      id="Home"
    >
      <Navbar />
      <div className="container mx-auto flex items-center justify-start min-h-screen px-6 md:px-20 lg:px-32">
        <motion.div
          initial={{ opacity: 0, y: 100 }}
          transition={{ duration: 1.5 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-white text-left sm:text-center"
        >
          <h2 className="text-4xl sm:text-5xl md:text-[68px] font-semibold leading-tight max-w-3xl">
            Understand Your <br className="hidden md:block" /> Health Smarter
          </h2>

          <p className="text-lg sm:text-xl mt-4 text-gray-200 max-w-xl">
            Get trustworthy medical answers powered by AI
          </p>

          <div className="mt-12 flex justify-start">
            <button
              onClick={handleClick}
              className="border border-white px-8 py-2 rounded flex items-center justify-between w-full max-w-xs sm:max-w-sm md:max-w-md lg:max-w-lg text-white hover:bg-amber-50 hover:text-black transition duration-300"
            >
              <span className="text-lg font-medium">Click Here</span>
              <img src={right_arrow} alt="arrow" className="w-3" />
            </button>
          </div>
        </motion.div>
      </div>
    </div>
  );
};

export default Home;
