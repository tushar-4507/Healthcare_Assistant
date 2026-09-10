import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import Navbar from "../components/Navbar";
import { toast } from "react-toastify";
import { useAuth } from "../context/AuthContext";

const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [mobile, setMobile] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      await login(mobile, password);
      toast.success("Login successful!");
      navigate("/main");
    } catch (error) {
      toast.error(error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-purple-100 to-purple-200">
      <Navbar solidBackground={true} />
      <div className="flex justify-center items-center h-[calc(100vh-80px)] px-4 pt-20">
        <form
          onSubmit={handleLogin}
          className="w-full max-w-md bg-white p-6 rounded-2xl shadow-2xl"
        >
          <h2 className="text-2xl font-bold mb-4 text-center">Login</h2>
          <div className="mb-4">
            <label>Mobile Number</label>
            <input
              type="tel"
              value={mobile}
              onChange={(e) => setMobile(e.target.value.replace(/[^0-9]/g, ""))}
              maxLength={10}
              required
              className="w-full px-4 py-2 border rounded mt-1"
            />
          </div>
          <div className="mb-4">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full px-4 py-2 border rounded mt-1"
            />
          </div>
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-purple-600 text-white py-2 rounded mt-2 disabled:opacity-60"
          >
            {isSubmitting ? "Logging in..." : "Login"}
          </button>
          <p className="mt-4 text-center text-gray-600">
            Not registered yet?{" "}
            <Link to="/signup" className="text-purple-600 font-semibold">
              Sign Up
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
};

export default Login;
