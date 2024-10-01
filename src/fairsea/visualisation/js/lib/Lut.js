class Lut {

    ColorMapKeywords = {
        'rainbow': [[0.0, 0x0000FF],[0.2, 0x00FFFF],[0.5, 0x00FF00],[0.8, 0xFFFF00],[1.0, 0xFF0000]],
        'cooltowarm': [[0.0, 0x3C4EC2],[0.2, 0x9BBCFF],[0.5, 0xDCDCDC],[0.8, 0xF6A385],[1.0, 0xB40426]],
        'blackbody': [[0.0, 0x000000],[0.2, 0x780000],[0.5, 0xE63200],[0.8, 0xFFFF00],[1.0, 0xFFFFFF]],
        'grayscale': [[0.0, 0x000000],[0.2, 0x404040],[0.5, 0x7F7F80],[0.8, 0xBFBFBF],[1.0, 0xFFFFFF]]
    };

    constructor(colormap, count = 32) {
        this.isLut = true;
        this.lut = [];
        this.map = [];
        this.n = 0;
        this.minV = 0;
        this.maxV = 1;

        this.setColorMap(colormap, count);
    }

    set(value) {
        if (value.isLut === true) {
            this.copy(value);
        }
        return this;
    }

    setMin(min) {
        this.minV = min;
        return this;
    }

    setMax(max) {
        this.maxV = max;
        return this;
    }

    setColorMap(colormap, count = 32) {
        this.map = this.ColorMapKeywords[colormap] || this.ColorMapKeywords.rainbow;
        this.n = count;

        const step = 1.0 / this.n;
        const minColor = new Color();
        const maxColor = new Color();

        this.lut.length = 0;

        // sample at 0
        this.lut.push(new Color(this.map[0][1]));

        // sample at 1/n, ..., (n-1)/n
        for (let i = 1; i < count; i++) {
            const alpha = i * step;
            for (let j = 0; j < this.map.length - 1; j++) {
                if (alpha > this.map[j][0] && alpha <= this.map[j + 1][0]) {
                    const min = this.map[j][0];
                    const max = this.map[j + 1][0];

                    minColor.set(this.map[j][1]);
                    maxColor.set(this.map[j + 1][1]);

                    const color = new Color().lerpColors(minColor, maxColor, (alpha - min) / (max - min));
                    this.lut.push(color);
                }
            }

        }

        // sample at 1
        this.lut.push(new Color(this.map[this.map.length - 1][1]));

        return this;
    }

    copy(lut) {
        this.lut = lut.lut;
        this.map = lut.map;
        this.n = lut.n;
        this.minV = lut.minV;
        this.maxV = lut.maxV;

        return this;
    }

    getColor(alpha) {
        alpha = Math.max(this.minV, Math.min(this.maxV, alpha) );
        alpha = (alpha - this.minV) / (this.maxV - this.minV);
        const colorPosition = Math.round(alpha * this.n);
        return this.lut[colorPosition];
    }

    addColorMap(name, arrayOfColors) {
        this.ColorMapKeywords[name] = arrayOfColors;
        return this;
    }
}