import { useEffect, useRef, useState } from 'react';

/**
 * NumberTicker — анимированный счётчик числа (адаптация компонента Magic UI
 * number-ticker: оригинал использует motion/react + useInView + Tailwind,
 * здесь — IntersectionObserver + rAF без зависимостей, т.к. в проекте нет Tailwind).
 *
 * Как в оригинале, анимация стартует при появлении элемента во viewport.
 * Без IntersectionObserver (jsdom в тестах) или при prefers-reduced-motion
 * сразу показываем финальное значение.
 */
export default function NumberTicker({ value, suffix = '', duration = 900 }) {
  const target = Number(value) || 0;
  const spanRef = useRef(null);
  const frameRef = useRef(null);

  const canAnimate =
    typeof window !== 'undefined' &&
    typeof window.IntersectionObserver === 'function' &&
    !(typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  const [display, setDisplay] = useState(canAnimate ? 0 : target);

  useEffect(() => {
    if (!canAnimate) {
      setDisplay(target);
      return undefined;
    }

    const animate = () => {
      const start = performance.now();
      const tick = (now) => {
        const progress = Math.min((now - start) / duration, 1);
        // easeOutExpo — быстрый старт, мягкое торможение (Apple HIG)
        const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
        setDisplay(Math.round(target * eased));
        if (progress < 1) frameRef.current = requestAnimationFrame(tick);
      };
      frameRef.current = requestAnimationFrame(tick);
    };

    const observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) {
        observer.disconnect();
        animate();
      }
    });
    if (spanRef.current) observer.observe(spanRef.current);

    return () => {
      observer.disconnect();
      cancelAnimationFrame(frameRef.current);
    };
  }, [target, duration, canAnimate]);

  return (
    <span ref={spanRef} style={{ fontVariantNumeric: 'tabular-nums' }}>
      {display.toLocaleString('ru-RU')}{suffix}
    </span>
  );
}
