import React from "react";
import { toast } from "react-toastify";
import { motion } from "motion/react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const Contact = () => {
  const [result, setResult] = React.useState("");
  const navigate = useNavigate();
  const { user } = useAuth();

  const onSubmit = async (event) => {
    if (!user) {
      event.preventDefault();
      toast.info("Please login first");
      navigate("/login");
      return;
    }

    event.preventDefault();
    setResult("Sending....");
    const formData = new FormData(event.target);
    formData.append("access_key", import.meta.env.VITE_WEB3FORM_ACCESS_KEY);

    const response = await fetch("https://api.web3forms.com/submit", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();

    if (data.success) {
      setResult("");
      toast.success("Form Submitted Successfully");
      event.target.reset();
    } else {
      console.log("Error", data);
      toast.error(data.message);
      setResult("");
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: -200 }}
      transition={{ duration: 1 }}
      whileInView={{ opacity: 1, x: 0 }}
      viewport={{ once: true }}
      className="w-full overflow-hidden bg-blue-100"
      id="Contact"
    >
      <div className="text-center mt-4 p-6 py-20 lg:px-32">
        <h1 className="text-2xl sm:text-4xl font-bold mb-2 text-center">
          Contact{" "}
          <span className="underline underline-offset-4 decoration-1 font-light">
            With Us
          </span>
        </h1>
        <p className="text-center text-gray-500 mb-15 max-w-80 mx-auto">
          Your Health Matters. Contact Us for <br /> Reliable Support.
        </p>

        <form
          onSubmit={onSubmit}
          className="max-w-2xl mx-auto text-gray-600 pt-8"
        >
          <div className="flex flex-wrap">
            <div className="w-full md:w-1/2 text-left">
              Your Name
              <input
                className="w-full border border-gray-400 rounded py-3 px-4 mt-2"
                type="text"
                name="Name"
                placeholder="Your Name"
                required
              />
            </div>
            <div className="w-full md:w-1/2 text-left md:pl-4 mt-6 md:mt-0">
              Mobile No
              <input
                className="w-full border border-gray-400 rounded py-3 px-4 mt-2"
                type="tel"
                name="mobile"
                placeholder="Your Mobile Number"
                required
                maxLength={10}
                onInput={(e) => {
                  e.target.value = e.target.value.replace(/[^0-9]/g, "");
                }}
              />
            </div>
          </div>
          <div className="my-6 text-left">
            Message
            <textarea
              className="w-full border border-gray-400 rounded py-3 px-4 mt-2 h-38 resize-none"
              name="Message"
              placeholder="Message"
              required
            ></textarea>
          </div>
          <button className="bg-blue-600 text-white py-2 px-12 mb-10 rounded">
            {result ? result : "Send Message"}
          </button>
        </form>
      </div>
    </motion.div>
  );
};

export default Contact;
