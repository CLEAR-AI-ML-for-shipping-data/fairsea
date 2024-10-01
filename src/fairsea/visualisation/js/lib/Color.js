class Color {

    constructor(r, g, b) {
        this.isColor = true;

        this.r = 1;
        this.g = 1;
        this.b = 1;

        if (g === undefined && b === undefined) {
            // r is Color, hex or string
            return this.set(r);
        }

        return this.setRGB(r, g, b);
    }

    set(value) {
        if (value && value.isColor) {
            this.copy(value);
        } else if (typeof value === 'number') {
            this.setHex(value);
        }
        return this;
    }

    setScalar(scalar) {
        this.r = scalar;
        this.g = scalar;
        this.b = scalar;
        return this;
    }

    setHex(hex) {
        hex = Math.floor(hex);
        this.r = (hex >> 16 & 255) / 255;
        this.g = (hex >> 8 & 255) / 255;
        this.b = (hex & 255) / 255;

        return this;
    }

    setRGB(r, g, b) {
        this.r = r;
        this.g = g;
        this.b = b;

        return this;
    }

    clone() {
        return new this.constructor(this.r, this.g, this.b);
    }

    copy(color) {
        this.r = color.r;
        this.g = color.g;
        this.b = color.b;

        return this;
    }


    getHex() {
        const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
        return Math.round(clamp(this.r * 255, 0, 255)) * 65536 + Math.round(clamp(this.g * 255, 0, 255)) * 256 + Math.round(clamp(this.b * 255, 0, 255));
    }

    getHexString() {
        return ('000000' + this.getHex().toString(16)).slice(-6);
    }

    getRGB(target) {
        target.r = this.r;
        target.g = this.g;
        target.b = this.b;

        return target;
    }

    add(color) {
        this.r += color.r;
        this.g += color.g;
        this.b += color.b;

        return this;
    }

    addColors(color1, color2) {
        this.r = color1.r + color2.r;
        this.g = color1.g + color2.g;
        this.b = color1.b + color2.b;

        return this;
    }

    addScalar(s) {
        this.r += s;
        this.g += s;
        this.b += s;

        return this;
    }

    sub(color) {
        this.r = Math.max(0, this.r - color.r);
        this.g = Math.max(0, this.g - color.g);
        this.b = Math.max(0, this.b - color.b);

        return this;
    }

    multiply(color) {
        this.r *= color.r;
        this.g *= color.g;
        this.b *= color.b;

        return this;
    }

    multiplyScalar(s) {
        this.r *= s;
        this.g *= s;
        this.b *= s;

        return this;
    }

    lerp(color, alpha) {
        this.r += (color.r - this.r) * alpha;
        this.g += (color.g - this.g) * alpha;
        this.b += (color.b - this.b) * alpha;

        return this;
    }

    lerpColors(color1, color2, alpha) {
        this.r = color1.r + (color2.r - color1.r) * alpha;
        this.g = color1.g + (color2.g - color1.g) * alpha;
        this.b = color1.b + (color2.b - color1.b) * alpha;

        return this;
    }

    equals(c) {
        return (c.r === this.r) && (c.g === this.g) && (c.b === this.b);
    }

    fromArray(array, offset = 0) {
        this.r = array[offset];
        this.g = array[offset + 1];
        this.b = array[offset + 2];

        return this;
    }

    toArray(array = [], offset = 0) {
        array[offset] = this.r;
        array[offset + 1] = this.g;
        array[offset + 2] = this.b;

        return array;
    }


    toJSON() {
        return this.getHex();
    }

    *
    [Symbol.iterator]() {
        yield this.r;
        yield this.g;
        yield this.b;
    }

}