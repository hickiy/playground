<!-- works normally -->
<script lang="jsx">
import WrapComponent from "./wrapComponent.jsx";
export default {
  setup() {
    return () => (
      <WrapComponent>
        <div>from parent component</div>
      </WrapComponent>
    );
  },
};
</script>

<style scoped lang="scss"></style>
