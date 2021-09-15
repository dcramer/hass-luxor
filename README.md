# Luxor Component for Home Assistant

[![hacs][hacsbadge]][hacs]

_Component to integrate with [FXLuminaire's Luxor][luxor] lighting system._

This will make all Luxor groups available as `light` entities, exposing the brightness functionality. Unfortunately colors cannot be exposed due to the way Luxor defines and utilizes them.

Additionally it will expose all themes as `scene` entities.

[luxor]: https://www.fxl.com/product/transformers/designer/luxor
[hacs]: https://github.com/custom-components/hacs
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
