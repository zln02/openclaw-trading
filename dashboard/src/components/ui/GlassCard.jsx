import PropTypes from "prop-types";

export default function GlassCard({
  children,
  className = "",
  delay = 0,
  style,
  as: Component = "section",
  accent = false,
}) {
  return (
    <div className="card-reveal" style={{ animationDelay: `${delay}s` }}>
      <Component className={`glass-card ${accent ? "glass-card--accent" : ""} ${className}`.trim()} style={style}>
        {children}
      </Component>
    </div>
  );
}

GlassCard.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  delay: PropTypes.number,
  style: PropTypes.object,
  as: PropTypes.string,
  accent: PropTypes.bool,
};
